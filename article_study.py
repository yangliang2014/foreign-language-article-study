#!/usr/bin/env python3
"""
article_study.py — 英文文章抓取 + 逐句精读上下排版注入（一体化工具）

子命令:
  prep       <url> -d dir [--normalize]              一条龙：抓取 + 骨架 + 实体体检 + draft 模板
  fetch      <url> [-o out.html]                     抓取文章，保存为单文件离线 HTML
  paragraphs <html>                                  打印正文段落（JSON），供撰写分析
  skeleton   <html> -o analysis.json [--normalize]   生成分析 JSON 骨架（自动断句 + 实体体检）
  draft      -j analysis.json -o draft.md            从骨架生成待填 draft（助手只写中文）
  fill       <draft.md> -j analysis.json [-o out]    draft 合并回 JSON（hl 留空自动取 ph）
  check      <html> -j analysis.json                 只校验分析 JSON，不写文件
  inject     <html> -j analysis.json [-o out.html]   把逐句分析注入 HTML（默认就地改写，自动备份）
  verify     <injected.html> [-j analysis.json]      注入结果静态验收（空字段/豆腐块/实体/词汇表/页高）
  shot       <html> [-d dir] [-P part_px]            CDP 全页四图（浅/深×精读/原文）+ 可读分片
  open       <html>                                  用系统默认浏览器打开成品

分析 JSON 结构见同目录 SKILL.md。
"""
import argparse
import base64
import gzip
import json
import os
import html as ihtml
import re
import shutil
import subprocess
import sys
import urllib.request
import urllib.parse
from datetime import datetime
from html.parser import HTMLParser

# ============================================================
# 第一部分：抓取（与 fetch_article.py 行为一致）
# ============================================================
UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"}


# ---------- 极简 DOM ----------
class Node:
    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.parent = parent
        self.children = []
        self.text = ""  # 文本节点用 tag=None

    def get_attr(self, name):
        for k, v in self.attrs.items():
            if k.lower() == name.lower():
                return v
        return None

    def inner_text(self):
        if self.tag is None:
            return self.text
        return "".join(c.inner_text() for c in self.children)


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(Node(None, parent=self.stack[-1]))
        self.stack[-1].children[-1].text = data


def find_all(node, pred, out=None):
    if out is None:
        out = []
    if node.tag and pred(node):
        out.append(node)
    for c in node.children:
        find_all(c, pred, out)
    return out


# ---------- 抓取 ----------
def _curl_to_file(url, timeout, use_env_proxy, dest):
    """用 curl 下载到指定文件，返回 (content_type, final_url)。"""
    env = None if use_env_proxy else {k: v for k, v in os.environ.items()
                                      if not re.match(r"(?i)^(https?_proxy|all_proxy|no_proxy)$", k)}
    cmd = [
        "curl", "-sSL", "--compressed",
        "--max-time", str(timeout),
        "-A", UA,
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/*;q=0.8,*/*;q=0.7",
        "-H", "Accept-Language: en-US,en;q=0.9",
        "-o", dest,
        "-w", "%{url_effective}\t%{content_type}",
    ]
    if not use_env_proxy:
        cmd.append("--noproxy")
        cmd.append("*")
    cmd.append(url)
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout + 10, env=env)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"curl exit {proc.returncode}")
    parts = (proc.stdout.split("\t", 1) + ["", ""])[:2] if proc.stdout else ["", ""]
    return parts[1].strip(), parts[0].strip() or url


def _curl(url, timeout, use_env_proxy):
    import tempfile
    fd, body_path = tempfile.mkstemp()
    os.close(fd)
    try:
        ctype, final_url = _curl_to_file(url, timeout, use_env_proxy, body_path)
        with open(body_path, "rb") as f:
            data = f.read()
        return data, ctype, final_url
    finally:
        os.unlink(body_path)


def http_get(url, timeout=25):
    # 先直连（忽略失效的本地代理），失败再走环境里的代理
    try:
        return _curl(url, timeout, use_env_proxy=False)
    except Exception:
        return _curl(url, timeout, use_env_proxy=True)


def download_to(url, dest, timeout=300):
    """大文件下载：先直连再走环境代理，直接落盘到 dest。"""
    try:
        return _curl_to_file(url, timeout, use_env_proxy=False, dest=dest)
    except Exception:
        return _curl_to_file(url, timeout, use_env_proxy=True, dest=dest)


def chrome_dump_dom(url, timeout=90):
    """用本机 headless Chrome 渲染后 dump DOM。

    部分站点（如 New Scientist）在边缘按 TLS/客户端指纹拦截非浏览器请求，
    curl 无论换什么 UA 都拿到 406/空 body，只能由真实浏览器取回页面。
    返回渲染后的 HTML 文本；无 Chrome 或失败时返回 None。
    """
    import tempfile
    chrome = find_chrome()
    if not chrome:
        print("  未找到 Chrome/Chromium/Edge，跳过浏览器渲染回退（可用 CHROME 环境变量指定）",
              file=sys.stderr)
        return None
    profile = tempfile.mkdtemp(prefix="chrome-fetch-")
    proxy = os.environ.get("https_proxy") or os.environ.get("http_proxy")
    try:
        for headless in ("--headless=new", "--headless"):
            cmd = [chrome, headless, "--disable-gpu", "--no-first-run",
                   "--disable-blink-features=AutomationControlled",
                   f"--user-data-dir={profile}",
                   "--virtual-time-budget=20000", "--dump-dom", url]
            if proxy:
                cmd[4:4] = [f"--proxy-server={proxy}"]
            try:
                proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                continue
            if proc.returncode == 0 and len(proc.stdout) > 500:
                return proc.stdout.decode("utf-8", "replace")
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    return None


# ---------- 正文定位 ----------
CONTENT_HINTS = re.compile(
    r"article[_\-]?(content|body|main)|entry[_\-]?content|post[_\-]?content|story[_\-]?body|article-body", re.I)


def para_score(node):
    score = 0
    for p in find_all(node, lambda n: n.tag == "p"):
        t = p.inner_text().strip()
        if len(t) > 60:
            score += len(t)
    return score


def locate_content(root):
    candidates = find_all(root, lambda n: n.tag in ("article", "main") or
                          (n.get_attr("class") and CONTENT_HINTS.search(n.get_attr("class") or "")) or
                          (n.get_attr("id") and CONTENT_HINTS.search(n.get_attr("id") or "")))
    if candidates:
        best = max(candidates, key=para_score)
        if para_score(best) > 300:
            return best
    # 兜底：全页找 <p> 文字最密集的容器
    divs = find_all(root, lambda n: n.tag in ("div", "section", "td"))
    scored = [(para_score(d), d) for d in divs]
    scored = [s for s in scored if s[0] > 300]
    if scored:
        return max(scored, key=lambda x: x[0])[1]
    return root


# ---------- 内容提取 ----------
SKIP_TAGS = {"script", "style", "nav", "footer", "aside", "form",
             "noscript", "iframe", "svg", "button"}


# 显式指向原图/大图的懒加载属性
HIRES_DATA_ATTRS = ("data-original", "data-full", "data-hi-res-src",
                    "data-high-res-src", "data-highres", "data-zoom",
                    "data-large", "data-big", "data-raw", "data-ultra-src")
# 普通懒加载属性，只比写死的 src 稍优先
LAZY_DATA_ATTRS = ("data-lazy-src", "data-src")
SRCSET_ATTRS = ("srcset", "data-srcset")


def parse_srcset(srcset):
    """解析 srcset，返回 [(score, url)]；score 按声明的宽度(w)/像素密度(x)。"""
    out = []
    for item in srcset.split(","):
        parts = item.strip().split()
        if not parts:
            continue
        url, score = parts[0], 0
        if len(parts) > 1:
            desc = parts[-1]
            try:
                if desc.endswith("w"):
                    score = int(desc[:-1])
                elif desc.endswith("x"):
                    score = int(float(desc[:-1]) * 1000)
            except ValueError:
                score = 0
        out.append((score, url))
    return out


def img_candidates(node):
    """收集一个 <img> 上声明的全部图片候选，分数越高越清晰。"""
    cands = []
    for a in SRCSET_ATTRS:
        v = node.get_attr(a)
        if v:
            cands.extend(parse_srcset(v))
    for a in HIRES_DATA_ATTRS:
        v = node.get_attr(a)
        if v:
            cands.append((9000, v))  # CDN srcset 宽度一般不超过 4000
    for a in LAZY_DATA_ATTRS:
        v = node.get_attr(a)
        if v:
            cands.append((100, v))
    v = node.get_attr("src")
    if v:
        cands.append((0, v))
    return cands


# URL 查询串里表示动态缩放的参数（WordPress/Photon、imgix 等）
SIZING_PARAMS = {"w", "h", "width", "height", "resize", "fit", "crop"}


def original_variant(url):
    """去掉缩放参数还原原图 URL；没有可去的参数时返回 None。"""
    p = urllib.parse.urlsplit(url)
    if not p.query:
        return None
    qs = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
    kept = [(k, v) for k, v in qs if k.lower() not in SIZING_PARAMS]
    if len(kept) == len(qs):
        return None
    query = urllib.parse.urlencode(kept)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, query, ""))


def ranked_urls(cands, base):
    """候选按清晰度降序去重；再把最高清 URL 还原出的原图排在最前。"""
    cands = sorted((s for s in cands if s[1]), reverse=True)
    urls = []
    for _, u in cands:
        au = urllib.parse.urljoin(base, u.strip())
        if au not in urls:
            urls.append(au)
    if urls:
        orig = original_variant(urls[0])
        if orig and orig not in urls:
            urls.insert(0, orig)
    return urls


def img_urls(node, base):
    return ranked_urls(img_candidates(node), base)


def picture_urls(pic, base):
    """从 <picture> 的 <source srcset> 和 <img> 中选最清晰候选。"""
    cands = []
    for s in find_all(pic, lambda n: n.tag == "source"):
        mtype = s.get_attr("type") or ""
        if mtype and not mtype.startswith("image/"):
            continue  # 跳过 video/ 等非图片 source
        for a in SRCSET_ATTRS:
            v = s.get_attr(a)
            if v:
                cands.extend(parse_srcset(v))
    for im in find_all(pic, lambda n: n.tag == "img"):
        cands.extend(img_candidates(im))
    return ranked_urls(cands, base)


# ---------- 视频提取 ----------
VIDEO_LAZY_ATTRS = ("data-video-src", "data-video-url", "data-src",
                    "data-video", "data-mp4", "data-stream-url", "data-stream")
VIDEO_EXT = {"video/mp4": ".mp4", "video/webm": ".webm",
             "video/ogg": ".ogv", "video/quicktime": ".mov",
             "video/x-m4v": ".m4v"}


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def video_format_rank(url, mtype=""):
    """mp4 兼容性最好排最前，其次 webm、ogg。"""
    if mtype:
        if "mp4" in mtype or "quicktime" in mtype or "m4v" in mtype:
            return 3
        if "webm" in mtype:
            return 2
        if "ogg" in mtype:
            return 1
    path = urllib.parse.urlsplit(url).path.lower()
    if path.endswith((".mp4", ".mov", ".m4v")):
        return 3
    if path.endswith(".webm"):
        return 2
    if path.endswith((".ogv", ".ogg")):
        return 1
    return 0


def video_info(video_node, base):
    """收集 <video> 的全部候选视频 URL（按兼容性/清晰度排序）和封面图。"""
    cands = []
    for s in find_all(video_node, lambda n: n.tag == "source"):
        mtype = (s.get_attr("type") or "").split(";")[0].strip()
        h = _int(s.get_attr("data-height") or s.get_attr("height"))
        for a in ("src",) + VIDEO_LAZY_ATTRS:
            v = s.get_attr(a)
            if v:
                cands.append((video_format_rank(v, mtype), h, v))
    h = _int(video_node.get_attr("data-height") or video_node.get_attr("height"))
    for a in ("src",) + VIDEO_LAZY_ATTRS:
        v = video_node.get_attr(a)
        if v:
            cands.append((video_format_rank(v), h, v))
    cands.sort(key=lambda c: (c[0], c[1]), reverse=True)
    urls = []
    for _, _, u in cands:
        au = urllib.parse.urljoin(base, u.strip())
        if urllib.parse.urlsplit(au).path.lower().endswith(".m3u8"):
            continue  # HLS 只是播放列表，无法直接保存
        if au not in urls:
            urls.append(au)
    poster = video_node.get_attr("poster")
    poster = urllib.parse.urljoin(base, poster.strip()) if poster else None
    return urls, poster


def has_ancestor(node, tag):
    p = node.parent
    while p is not None:
        if p.tag == tag:
            return True
        p = p.parent
    return False


def link_dense(node):
    text = node.inner_text().strip()
    if len(text) < 40:
        return False
    link_text = "".join(a.inner_text() for a in find_all(node, lambda n: n.tag == "a")).strip()
    long_paras = [p for p in find_all(node, lambda n: n.tag == "p") if len(p.inner_text().strip()) > 80]
    return len(link_text) / max(len(text), 1) > 0.7 and len(long_paras) == 0


def extract_blocks(content, base):
    blocks = []

    def walk(node):
        if node.tag in SKIP_TAGS:
            return
        if node.tag in ("div", "section") and link_dense(node):
            return
        cls = " ".join(filter(None, [node.get_attr("class") or "", node.get_attr("id") or ""]))
        if re.search(r"share|social|newsletter|subscribe|related|recommend|promo|advert|sidebar|comment|cookie|signup|caption|credit|byline", cls, re.I):
            return
        if node.tag == "figure":
            cap_node = next(iter(find_all(node, lambda n: n.tag == "figcaption")), None)
            cap = cap_node.inner_text().strip() if cap_node else ""
            vids = find_all(node, lambda n: n.tag == "video")
            if vids:
                for v in vids:
                    urls, poster = video_info(v, base)
                    if urls:
                        blocks.append(("video", (urls, poster, cap)))
                return  # 有视频时忽略同 figure 里的封面图，避免重复
            for pic in find_all(node, lambda n: n.tag == "picture"):
                urls = picture_urls(pic, base)
                if urls:
                    blocks.append(("img", (urls, cap)))
            for im in find_all(node, lambda n: n.tag == "img"):
                if has_ancestor(im, "picture"):
                    continue  # 已随 <picture> 处理，避免重复
                urls = img_urls(im, base)
                if urls:
                    blocks.append(("img", (urls, cap)))
            return
        if node.tag == "picture":
            urls = picture_urls(node, base)
            if urls:
                blocks.append(("img", (urls, "")))
            return
        if node.tag == "video":
            urls, poster = video_info(node, base)
            if urls:
                blocks.append(("video", (urls, poster, "")))
            return
        if node.tag in ("h2", "h3", "h4"):
            t = node.inner_text().strip()
            if t:
                blocks.append((node.tag, t))
            return
        if node.tag == "p":
            t = re.sub(r"\s+", " ", node.inner_text()).strip()
            for im in find_all(node, lambda n: n.tag == "img"):
                if has_ancestor(im, "picture"):
                    continue
                urls = img_urls(im, base)
                if urls:
                    blocks.append(("img", (urls, "")))
            if len(t) > 30:
                blocks.append(("p", t))
            return
        if node.tag in ("ul", "ol"):
            items = [li.inner_text().strip() for li in find_all(node, lambda n: n.tag == "li")]
            items = [re.sub(r"\s+", " ", i) for i in items if i.strip()]
            if items:
                blocks.append(("list", (node.tag, items)))
            return
        if node.tag == "img":
            urls = img_urls(node, base)
            if urls:
                blocks.append(("img", (urls, "")))
            return
        for c in node.children:
            walk(c)

    walk(content)
    return blocks


def dedupe(blocks):
    out, seen_p, seen_img, seen_vid = [], set(), set(), set()
    for kind, val in blocks:
        if kind == "p":
            if val in seen_p:
                continue
            seen_p.add(val)
        if kind == "img":
            if val[0][0] in seen_img:
                continue
            seen_img.add(val[0][0])
        if kind == "video":
            if val[0][0] in seen_vid:
                continue
            seen_vid.add(val[0][0])
        out.append((kind, val))
    return out


# ---------- 图片内嵌 ----------
def embed_image(url):
    try:
        data, ctype, _ = http_get(url, timeout=20)
    except Exception:
        return None
    if len(data) < 2000:  # 跳过图标/像素
        return None
    if "image" not in ctype:
        sniff = data[:12]
        if sniff.startswith(b"\xff\xd8"):
            ctype = "image/jpeg"
        elif sniff.startswith(b"\x89PNG"):
            ctype = "image/png"
        elif sniff[:4] == b"RIFF" and sniff[8:12] == b"WEBP":
            ctype = "image/webp"
        elif b"GIF" in sniff[:6]:
            ctype = "image/gif"
        else:
            return None
    else:
        ctype = ctype.split(";")[0].strip()
    return f"data:{ctype};base64," + base64.b64encode(data).decode()


# ---------- 视频下载 ----------
def sniff_video(head):
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "video/mp4"  # ISO BMFF：mp4/mov/m4v 同属此类
    if head[:4] == b"\x1aE\xdf\xa3":
        return "video/webm"
    if head[:4] == b"OggS":
        return "video/ogg"
    return None


def download_video(url, media_dir, base_name):
    """下载视频并校验真实容器类型，成功返回文件名，失败返回 None。"""
    if urllib.parse.urlsplit(url).path.lower().endswith(".m3u8"):
        print("  跳过 HLS 流(m3u8)，无法直接保存", file=sys.stderr)
        return None
    os.makedirs(media_dir, exist_ok=True)
    partial = os.path.join(media_dir, "." + base_name + ".part")
    try:
        ctype, _ = download_to(url, partial, timeout=300)
    except Exception as e:
        print(f"  下载失败: {e}", file=sys.stderr)
        if os.path.exists(partial):
            os.unlink(partial)
        return None
    size = os.path.getsize(partial)
    if size < 20000:
        print("  文件过小，疑似错误页，跳过", file=sys.stderr)
        os.unlink(partial)
        return None
    with open(partial, "rb") as f:
        head = f.read(16)
    ctype = ctype.split(";")[0].strip().lower()
    vtype = ctype if ctype.startswith("video/") else sniff_video(head)
    if not vtype:
        print(f"  不是有效视频(Content-Type: {ctype or '未知'})，跳过", file=sys.stderr)
        os.unlink(partial)
        return None
    ext = VIDEO_EXT.get(vtype)
    if not ext:
        ext = os.path.splitext(urllib.parse.urlsplit(url).path)[1].lower()
        if ext not in (".mp4", ".webm", ".ogv", ".ogg", ".mov", ".m4v"):
            ext = ".mp4"
    fname = base_name + ext
    os.replace(partial, os.path.join(media_dir, fname))
    print(f"  视频大小: {size / 1048576:.1f} MB", file=sys.stderr)
    return fname


# ---------- Arc XP / Fusion 回退 ----------
def _brace_match(s, start):
    """从 s[start]（'{'）开始做字符串感知的括号匹配，返回 JSON 子串。"""
    depth = 0
    i = start
    instr = False
    esc = False
    while i < len(s):
        c = s[i]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return s[start:i + 1]
        i += 1
    return None


def fusion_global_content(text):
    """提取页面里 Fusion.globalContent={...} 的 Arc XP 文章 JSON。"""
    m = re.search(r"Fusion\.globalContent\s*=\s*\{", text)
    if not m:
        return None
    sub = _brace_match(text, m.end() - 1)
    if not sub:
        return None
    try:
        return json.loads(sub)
    except Exception:
        return None


def arc_content_blocks(text, base):
    """从 Arc XP content_elements 按顺序构建段落/标题/图片块。"""
    data = fusion_global_content(text)
    if not data:
        return []
    blocks = []
    for el in data.get("content_elements", []):
        kind = el.get("type")
        if kind == "text":
            t = re.sub(r"\s+", " ", el.get("content", "")).strip()
            if t:
                blocks.append(("p", t))
        elif kind == "header":
            t = re.sub(r"\s+", " ", el.get("content", "")).strip()
            if not t:
                continue
            level = _int(el.get("level")) or 2
            htag = "h2" if level <= 2 else ("h3" if level == 3 else "h4")
            blocks.append((htag, t))
        elif kind == "image":
            ap = el.get("additional_properties", {})
            urls = []
            if ap.get("originalUrl"):
                urls.append(ap["originalUrl"])
            for a in ("fullSizeResizeUrl", "resizeUrl", "proxyUrl"):
                if ap.get(a):
                    urls.append(urllib.parse.urljoin(base, ap[a]))
            urls = [u for i, u in enumerate(urls) if u and u not in urls[:i]]
            if urls:
                blocks.append(("img", (urls, el.get("caption", "") or "")))
    return blocks


# ---------- schema.org JSON-LD articleBody 回退 ----------
def _jsonld_dicts(page_text):
    """迭代页面全部 JSON-LD <script> 里出现的 dict（含 @graph 内嵌节点）。"""
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                         page_text, re.S | re.I):
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue
        stack = [data]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                yield o
                stack.extend(o.values())
            elif isinstance(o, list):
                stack.extend(o)


def jsonld_article(page_text):
    """返回 schema.org 文章节点（含最长 articleBody 的 dict），没有则 None。

    不少付费墙站点（New Scientist 等）虽标记 isAccessibleForFree=false，
    仍把全文放进 JSON-LD 的 articleBody 供搜索引擎索引。
    """
    best = None
    for o in _jsonld_dicts(page_text):
        body = o.get("articleBody")
        if isinstance(body, str) and body.strip() and (
                best is None or len(body) > len(best["articleBody"])):
            best = o
    return best


def _jsonld_image_ref(node, by_id):
    """解析文章节点的 image 字段，返回 (urls, caption)。image 可能是
    URL 字符串、@id 引用、ImageObject dict 或它们的列表。"""
    urls, caption = [], None
    imgs = node.get("image")
    if isinstance(imgs, dict):
        imgs = [imgs]
    elif isinstance(imgs, str):
        imgs = [imgs]
    elif not isinstance(imgs, list):
        imgs = []
    for im in imgs:
        if isinstance(im, str):
            ref = by_id.get(im) or (by_id.get(im.lstrip("#")) if im.startswith("#") else None)
            if ref is not None:
                im = ref
            elif im.startswith("http"):
                urls.append(im)
                continue
            else:
                continue
        if isinstance(im, dict):
            if im.get("@id") and not im.get("contentUrl") and not im.get("url"):
                resolved = by_id.get(im["@id"]) or by_id.get(im["@id"].lstrip("#"))
                if resolved:
                    im = resolved
            for k in ("contentUrl", "url"):
                if isinstance(im.get(k), str) and im[k].startswith("http"):
                    urls.append(im[k])
            if isinstance(im.get("caption"), str):
                caption = im["caption"]
    seen = []
    for u in urls:
        if u not in seen:
            seen.append(u)
    return seen, caption


def jsonld_article_blocks(page_text, base):
    """从 JSON-LD articleBody 构建 img/p/h2 块；无 articleBody 时返回 []。"""
    art = jsonld_article(page_text)
    if not art:
        return []
    by_id = {}
    for o in _jsonld_dicts(page_text):
        if o.get("@id"):
            by_id[o["@id"]] = by_id.get(o["@id"], o)
    urls, caption = _jsonld_image_ref(art, by_id)
    chunks = [re.sub(r"\s+", " ", c).strip()
              for c in re.split(r"\n\s*\n", art["articleBody"]) if c.strip()]
    if not chunks:
        return []
    # 首块与题图 caption 一致时，它是图注而非正文段落
    if caption and chunks and re.sub(r"\s+", " ", caption).strip() == chunks[0]:
        chunks = chunks[1:]

    def is_heading(t):
        return len(t.split()) <= 6 and not t.endswith((".", "?", "!", '"', "”", "’"))

    blocks = []
    if urls:
        blocks.append(("img", (ranked_urls([(0, u) for u in urls], base),
                               re.sub(r"\s+", " ", caption or "").strip())))
    for t in chunks:
        blocks.append(("h2", t) if is_heading(t) else ("p", t))
    return blocks


# ---------- 元信息 ----------
def get_meta(root, prop):
    for m in find_all(root, lambda n: n.tag == "meta"):
        if (m.get_attr("property") or m.get_attr("name")) == prop and m.get_attr("content"):
            return m.get_attr("content").strip()
    return None


VIDEO_OG_PROPS = ("og:video", "og:video:url", "og:video:secure_url",
                  "twitter:player:stream")


def jsonld_video_urls(root):
    """从 JSON-LD 的 VideoObject.contentUrl 提取直链视频。"""
    urls = []

    def scan(o):
        if isinstance(o, dict):
            t = o.get("@type")
            types = t if isinstance(t, list) else [t]
            if any(str(x).lower() == "videoobject" for x in types):
                cu = o.get("contentUrl")
                if isinstance(cu, str) and cu.strip():
                    urls.append(cu.strip())
            for v in o.values():
                scan(v)
        elif isinstance(o, list):
            for v in o:
                scan(v)

    for s in find_all(root, lambda n: n.tag == "script"
                      and (n.get_attr("type") or "").lower() == "application/ld+json"):
        try:
            scan(json.loads(s.inner_text()))
        except Exception:
            continue
    return urls


# ---------- 输出 ----------
TEMPLATE = """<!DOCTYPE html>
<html lang="">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ margin:0; background:#fff; color:#1a1a1a;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; line-height:1.7; }}
  article {{ max-width:720px; margin:0 auto; background:#fff; padding:48px 40px 72px; min-height:100vh; box-sizing:border-box; }}
  h1 {{ font-size:34px; line-height:1.25; margin:0 0 24px; letter-spacing:-.01em; }}
  .meta {{ font-size:14px; color:#666; margin-bottom:28px; }}
  figure {{ margin:0 0 32px; }}
  figure img {{ width:100%; border-radius:6px; display:block; }}
  figure video {{ width:100%; border-radius:6px; display:block; background:#000; max-height:80vh; }}
  figcaption {{ font-size:13px; color:#666; margin-top:8px; }}
  figure.missing figcaption a {{ color:#888; word-break:break-all; }}
  h2 {{ font-size:26px; margin:36px 0 16px; }}
  h3 {{ font-size:21px; margin:28px 0 12px; }}
  p {{ font-size:18px; margin:0 0 20px; }}
  ul,ol {{ font-size:18px; margin:0 0 20px; padding-left:28px; }}
  li {{ margin-bottom:8px; }}
  .source {{ margin-top:40px; padding-top:16px; border-top:1px solid #e0e0de; font-size:13px; color:#888; word-break:break-all; }}
  .source a {{ color:#888; }}
  @media (prefers-color-scheme:dark) {{
    body {{ background:#14141a; color:#e8e8ea; }}
    article {{ background:#1d1d24; }}
    .meta,figcaption {{ color:#a0a0a8; }}
    .source {{ border-color:#33333c; color:#777; }} .source a {{ color:#777; }}
  }}
  @media (max-width:600px) {{ article {{ padding:28px 20px 48px; }} h1 {{ font-size:26px; }} p,ul,ol {{ font-size:17px; }} }}
</style>
</head>
<body>
<article>
  <h1>{title}</h1>
  {meta}
  {body}
  <p class="source">Source: <a href="{url}">{url}</a><br>Saved {saved_at}</p>
</article>
</body>
</html>
"""


def render(blocks, title, url, date, media_dir, media_name):
    parts, n_img, n_video = [], 0, 0
    for kind, val in blocks:
        if kind == "p":
            parts.append(f"<p>{ihtml.escape(val)}</p>")
        elif kind in ("h2", "h3", "h4"):
            parts.append(f"<{kind}>{ihtml.escape(val)}</{kind}>")
        elif kind == "list":
            tag, items = val
            lis = "".join(f"<li>{ihtml.escape(i)}</li>" for i in items)
            parts.append(f"<{tag}>{lis}</{tag}>")
        elif kind == "img":
            urls, cap = val
            data_uri = None
            for u in urls:  # 优先原图，失败依次回退
                print(f"  下载图片 {n_img + 1}: {u[:100]}", file=sys.stderr)
                data_uri = embed_image(u)
                if data_uri:
                    break
            if not data_uri:
                continue
            n_img += 1
            cap_html = f"<figcaption>{ihtml.escape(cap)}</figcaption>" if cap else ""
            parts.append(f'<figure><img src="{data_uri}" alt="">{cap_html}</figure>')
        elif kind == "video":
            urls, poster, cap = val
            href = None
            for u in urls:
                print(f"  下载视频: {u[:100]}", file=sys.stderr)
                fname = download_video(u, media_dir, f"video-{n_video + 1}")
                if fname:
                    n_video += 1
                    href = f"{media_name}/{fname}"
                    break
            if not href:
                cap_html = ('<figcaption>视频下载失败，可在线观看: '
                            f'<a href="{ihtml.escape(urls[0], quote=True)}">{ihtml.escape(urls[0])}</a></figcaption>')
                parts.append(f'<figure class="missing">{cap_html}</figure>')
                continue
            poster_uri = embed_image(poster) if poster else None
            poster_attr = f' poster="{poster_uri}"' if poster_uri else ""
            cap_html = f"<figcaption>{ihtml.escape(cap)}</figcaption>" if cap else ""
            parts.append(
                f'<figure class="video"><video controls preload="metadata"{poster_attr} '
                f'src="{ihtml.escape(href, quote=True)}"></video>{cap_html}</figure>')
    meta_html = f'<p class="meta">{ihtml.escape(date)}</p>' if date else ""
    return TEMPLATE.format(
        title=ihtml.escape(title), meta=meta_html, body="\n".join(parts),
        url=ihtml.escape(url, quote=True), saved_at=datetime.now().strftime("%Y-%m-%d %H:%M"))


def slugify(s, limit=60):
    s = re.sub(r"[^\w\s-]", "", s.lower()).strip()
    s = re.sub(r"[-\s]+", "-", s)
    return (s[:limit] if limit > 0 else s) or "article"


def extract_page(page_text, final_url):
    """解析一页 HTML 的元信息与正文块。返回 (root, title, date, blocks)。

    正文提取顺序：DOM 容器 → Arc/Fusion globalContent → schema.org JSON-LD
    articleBody；图片/视频缺失时再用 og:* meta 兜底。
    """
    builder = TreeBuilder()
    builder.feed(page_text)
    root = builder.root

    title = get_meta(root, "og:title") or ""
    site_name = get_meta(root, "og:site_name") or ""
    if site_name:
        title = re.sub(rf"\s*[|\-–—]\s*{re.escape(site_name)}\s*$", "", title, flags=re.I).strip()
    if not title:
        h1 = next(iter(find_all(root, lambda n: n.tag == "h1")), None)
        title = h1.inner_text().strip() if h1 else urllib.parse.urlparse(final_url).path.strip("/").split("/")[-1]

    date = get_meta(root, "article:published_time") or get_meta(root, "og:article:published_time") or ""
    if not date:
        art = jsonld_article(page_text)
        if art and art.get("datePublished"):
            date = art["datePublished"]
    if date:
        date = date[:10]

    content = locate_content(root)
    blocks = dedupe(extract_blocks(content, final_url))

    # DOM 提取可能只捞到导航/分享条里的零星段落；与 Arc/Fusion、JSON-LD
    # articleBody 候选比正文总量，明显更多者胜出（付费墙壳页面由此落到结构化数据）
    def p_len(bs):
        return sum(len(v) for k, v in bs if k == "p")

    dom_len = p_len(blocks)
    candidates = [(dom_len, blocks, "")]
    arc_blocks = arc_content_blocks(page_text, final_url)
    if arc_blocks:
        candidates.append((p_len(arc_blocks), arc_blocks, "Arc/Fusion 结构化数据"))
    ld_blocks = jsonld_article_blocks(page_text, final_url)
    if any(k == "p" for k, _ in ld_blocks):
        candidates.append((p_len(ld_blocks), ld_blocks, "schema.org JSON-LD articleBody"))
    best_len, best_blocks, best_src = max(candidates, key=lambda c: c[0])
    if best_src and best_len > dom_len + 200:
        print(f"使用 {best_src} 提取正文", file=sys.stderr)
        blocks = best_blocks
    if not any(k == "img" for k, _ in blocks):
        hero = (get_meta(root, "og:image") or get_meta(root, "og:image:secure_url")
                or get_meta(root, "twitter:image"))
        if hero:
            hero = ranked_urls([(0, hero.strip())], final_url)
            blocks.insert(0, ("img", (hero, "")))
    if not any(k == "video" for k, _ in blocks):
        vurls = [get_meta(root, p) for p in VIDEO_OG_PROPS]
        vurls = [v for v in vurls if v]
        if not vurls:
            vurls = jsonld_video_urls(root)
        abs_urls, seen = [], set()
        for v in vurls:
            au = urllib.parse.urljoin(final_url, v.strip())
            if au in seen or urllib.parse.urlsplit(au).path.lower().endswith(".m3u8"):
                continue
            seen.add(au)
            abs_urls.append(au)
        if abs_urls:
            blocks.insert(0, ("video", (abs_urls, None, "")))
    return root, title, date, blocks


def cmd_fetch(args):
    print(f"抓取: {args.url}", file=sys.stderr)
    raw, _, final_url = http_get(args.url)
    page_text = raw.decode("utf-8", "replace")
    root, title, date, blocks = extract_page(page_text, final_url)

    # curl 被边缘指纹拦截（406/403/空 body）或页面无可提取正文时，
    # 用本机 headless Chrome 渲染后再提取一次
    if not any(k == "p" for k, _ in blocks) or len(raw) < 500:
        print("curl 未取到正文，改用 headless Chrome 渲染抓取…", file=sys.stderr)
        dom = chrome_dump_dom(args.url)
        if dom:
            root2, title2, date2, blocks2 = extract_page(dom, args.url)
            if any(k == "p" for k, _ in blocks2):
                root, title, date, blocks = root2, title2, date2, blocks2
                final_url, page_text = args.url, dom
            else:
                root = root2  # 至少保留渲染后 DOM 的 meta（题图/视频兜底）

    p_count = sum(1 for k, _ in blocks if k == "p")
    v_count = sum(1 for k, _ in blocks if k == "video")
    print(f"标题: {title}", file=sys.stderr)
    print(f"提取段落: {p_count}", file=sys.stderr)
    print(f"发现视频: {v_count}", file=sys.stderr)
    if p_count == 0:
        print("⚠ 未提取到正文（可能该站不向爬虫开放全文）", file=sys.stderr)

    slug = slugify(title, limit=0) if args.dir else slugify(title)
    if args.output:
        out_path = args.output
    elif args.dir:
        out_dir = os.path.join(args.dir, slug)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, slug + ".html")
    else:
        out_path = slugify(title) + ".html"
    media_dir = os.path.splitext(os.path.abspath(out_path))[0] + "_media"
    media_name = os.path.basename(media_dir)
    out_html = render(blocks, title, final_url, date, media_dir, media_name)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out_html)
    try:
        os.rmdir(media_dir)  # 视频全部失败时清理空目录
    except OSError:
        pass
    print(f"已保存: {out_path}", file=sys.stderr)
    return out_path


# ============================================================
# 第二部分：逐句精读上下排版注入
# ============================================================
ANALYSIS_CSS = """
  /* ===== 逐句精读上下排版 · 柔和荧光笔配色（浅色默认，跟随系统自动深色）===== */
  :root {
    --bg:#f4f3ee; --card:#ffffff; --an-bg:#f8f7f2; --fg:#26241d; --fg-dim:#706d62;
    --line:#e5e2d7; --line2:#efede3; --en-border:#c9dec9;
    --hl:#fde9a6; --hl-fg:#5b490b;
    --g-bg:#e6eeff; --g-fg:#2751b8;
    --p-bg:#e3f3e8; --p-fg:#1c6b3f;
    --w-bg:#f6eccf; --w-fg:#836512;
    --accent:#1c6b3f; --on-accent:#ffffff; --bar:rgba(255,255,255,.93);
    --shadow:rgba(28,107,63,.28);
    --mono:"Andale Mono","SF Mono",Menlo,ui-monospace,Consolas,"DejaVu Sans Mono",
      "Courier New","PingFang SC","Microsoft YaHei",monospace;
  }
  @media (prefers-color-scheme:dark) {
    :root {
      --bg:#14161a; --card:#1c1f25; --an-bg:#20242b; --fg:#e8e7e0; --fg-dim:#9b998e;
      --line:#2f323a; --line2:#262931; --en-border:#3c4d42;
      --hl:#504418; --hl-fg:#f4df96;
      --g-bg:#22315a; --g-fg:#a9c2f5;
      --p-bg:#1e3326; --p-fg:#9fd8b0;
      --w-bg:#3b3218; --w-fg:#e9d58c;
      --accent:#86c79b; --on-accent:#15211a; --bar:rgba(28,31,37,.93);
      --shadow:rgba(134,199,155,.38);
    }
  }
  html, body { background:var(--bg); }
  body { color:var(--fg); font-family:var(--mono) !important; }
  article { max-width:1180px; background:var(--card) !important; color:var(--fg); }
  article h1, article h2, article h3 { color:var(--fg); font-family:var(--mono);
    letter-spacing:0; }
  article a { color:var(--g-fg); }
  .meta, figcaption, .source, .source a { color:var(--fg-dim) !important; }
  .source { border-color:var(--line2) !important; }
  /* 分析对比模式隐藏原文配图，只看原文模式再恢复 */
  article figure { display:none; }
  article.ana-off figure { display:block; margin:0 auto 32px; max-width:680px; }
  /* 纯原文模式配图：限宽居中，大图等比缩小、超高图封顶，小图保持原尺寸不放大 */
  article.ana-off figure img { width:auto; max-width:100%; max-height:70vh; margin:0 auto; }
  /* 有标题分析块时，分析模式隐藏原 h1，避免标题重复 */
  article h1.ana-dup { display:none; }
  article.ana-off h1.ana-dup { display:block; }

  /* 顶部阅读进度条 */
  #anaProg { position:fixed; top:0; left:0; right:0; height:3px; z-index:60; pointer-events:none;
    background:var(--line2); }
  #anaProg i { display:block; height:100%; width:0; background:var(--accent); }

  .ana-toolbar { position:sticky; top:0; z-index:40; display:flex; gap:10px; align-items:center;
    margin:0 0 22px; padding:9px 0; flex-wrap:wrap;
    background:var(--bar); backdrop-filter:blur(4px); border-bottom:1px solid var(--line2); }
  .ana-toolbar button { font:inherit; font-size:14px; padding:6px 16px; border-radius:4px;
    border:1px solid var(--accent); background:transparent; color:var(--accent); cursor:pointer;
    letter-spacing:1px; }
  .ana-toolbar button:hover { background:var(--accent); color:var(--on-accent); }
  .ana-toolbar button.playing { background:var(--accent); color:var(--on-accent); }
  .ana-toolbar kbd { font-family:var(--mono); font-size:11px; border:1px solid var(--line);
    border-radius:3px; padding:0 5px; color:var(--fg-dim); background:var(--an-bg); }
  .ana-toolbar .hint { font-size:13px; color:var(--fg-dim); }
  .ana-toolbar .tts-cfg { display:flex; gap:12px; align-items:center; margin-left:auto; }
  .ana-toolbar .tts-item { display:inline-flex; gap:5px; align-items:center;
    font-size:13px; color:var(--fg-dim); white-space:nowrap; }
  .ana-toolbar select { font:inherit; font-size:12.5px; color:var(--fg);
    background:var(--card); border:1px solid var(--line); border-radius:4px;
    padding:4px 6px; max-width:240px; cursor:pointer; }
  .ana-toolbar select:focus { border-color:var(--accent); outline:none; }
  @media (max-width:920px) { .ana-toolbar .tts-cfg { margin-left:0; gap:10px; } }
  .meta { margin:0 0 22px; }
  .pgrp { margin:0 0 28px; }
  .sa { display:grid; grid-template-columns:minmax(0,1fr);
    gap:10px; margin:0 0 16px; align-items:start; }
  .sa-en { position:relative; margin:0; font-size:16.5px; line-height:1.95;
    background:transparent; border:1px solid var(--line); border-left:4px solid var(--en-border);
    border-radius:4px; padding:13px 16px 13px 50px; transition:box-shadow .12s; color:var(--fg); }
  .sa-an { transition:box-shadow .12s; }
  /* 悬停一句：上下两块联动柔和描边 */
  .sa:hover .sa-en, .sa:hover .sa-an { box-shadow:0 0 0 1px var(--shadow); }
  /* 从原文高亮 Ctrl/⌘+点击 跳回本句分析后的定位闪烁 */
  .sa.sa-flash .sa-en, .sa.sa-flash .sa-an { box-shadow:0 0 0 2px var(--accent);
    transition:box-shadow .3s; }
  .sa.sa-flash { scroll-margin-top:80px; }
  .sa-en .sn { position:absolute; left:12px; top:13px; min-width:22px; text-align:center;
    font-size:12px; font-weight:400; color:var(--p-fg); background:var(--p-bg);
    border:1px solid transparent; border-radius:4px; padding:1px 6px;
    cursor:pointer; user-select:none; }
  .sa-en .sn:hover { background:var(--accent); color:var(--on-accent); }
  /* 句末朗读按钮 */
  .sa-en .sa-play { display:inline-flex; align-items:center; justify-content:center;
    vertical-align:1px; width:26px; height:23px; margin-left:8px; padding:0;
    border:1px solid var(--en-border); border-radius:4px; background:var(--card);
    color:var(--p-fg); cursor:pointer; transition:background .12s,color .12s,border-color .12s; }
  .sa-en .sa-play svg { width:13px; height:13px; display:block; }
  .sa-en .sa-play:hover, .sa-en .sa-play.playing { background:var(--accent);
    border-color:var(--accent); color:var(--on-accent); }
  /* 原文重点：柔和荧光笔黄 */
  .sa-en mark, .sa-en-title mark { background:var(--hl); color:var(--hl-fg); border-radius:3px;
    padding:0 3px; box-shadow:none; font-weight:600; }
  .sa-an { font-size:15px; line-height:1.85; background:var(--an-bg);
    border:1px solid var(--line2); border-radius:4px; padding:13px 16px; color:var(--fg); }
  .an-zh { margin-bottom:8px; color:var(--fg); }
  .an-gr { margin-bottom:8px; color:var(--fg); }
  /* 徽章：浅底彩字 */
  .sa-an .lab { display:inline-block; font-size:12.5px; font-weight:600; border-radius:4px;
    padding:1px 8px; margin-right:7px; vertical-align:1px; border:1px solid transparent; }
  .lab-zh { background:var(--p-bg); color:var(--p-fg); }
  .lab-gr { background:var(--g-bg); color:var(--g-fg); }
  .lab-ph { background:var(--w-bg); color:var(--w-fg); }
  .an-ph ul { margin:5px 0 0; padding:0; list-style:none; }
  .an-ph li { margin:0 0 5px; color:var(--fg); }
  /* 分析块高亮：语法术语＝淡蓝，短语＝淡绿 */
  mark.g { background:var(--g-bg); color:var(--g-fg); border-radius:3px; padding:0 4px; }
  mark.p { background:var(--p-bg); color:var(--p-fg); border-radius:3px; padding:0 4px;
    font-style:normal; font-weight:600; }
  /* 标题旁的“原文”外链标签 */
  .ana-orig { font-family:var(--mono); font-size:12px; font-weight:400; white-space:nowrap;
    margin-left:12px; padding:1px 8px; border:1px solid var(--g-fg); border-radius:4px;
    color:var(--g-fg) !important; text-decoration:none; letter-spacing:1px; }
  .ana-orig:hover { background:var(--g-fg); color:var(--card) !important; }
  .sa-title-wrap { margin:0 0 30px; }
  .sa-en-title { font-size:17.5px; line-height:1.9; background:transparent;
    border:1px solid var(--line); border-left:4px solid var(--en-border);
    border-radius:4px; padding:13px 16px; font-weight:600; color:var(--fg); }
  /* 文末重点短语词汇表 */
  .ana-gloss { margin:36px 0 8px; padding:20px 22px; background:var(--an-bg);
    border:1px solid var(--line2); border-radius:6px; }
  .ana-gloss h2 { font-size:16px; margin:0 0 14px; color:var(--fg); }
  .gl-list { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
    gap:7px 24px; }
  .gl-item { font-size:14px; display:flex; flex-wrap:wrap; gap:4px 8px; align-items:baseline; line-height:1.7; }
  .gl-item mark.p { white-space:normal; overflow-wrap:anywhere; }
  .gl-item span { flex:1 1 160px; color:var(--fg-dim); }
  article.ana-off .ana-gloss { display:none; }
  /* 回到顶部按钮 + 复制提示 */
  #anaTop { position:fixed; right:22px; bottom:26px; z-index:50; width:42px; height:42px;
    border-radius:4px; border:1px solid var(--accent); background:var(--card);
    color:var(--accent); font-size:18px; line-height:1; cursor:pointer; opacity:0;
    pointer-events:none; transition:opacity .2s; }
  #anaTop.show { opacity:1; pointer-events:auto; }
  #anaTop:hover { background:var(--accent); color:var(--on-accent); }
  .ana-toast { position:fixed; left:50%; bottom:40px; transform:translateX(-50%); z-index:70;
    background:var(--card); color:var(--fg); font-size:13px; padding:7px 16px;
    border:1px solid var(--accent); border-radius:4px; box-shadow:0 4px 18px rgba(0,0,0,.12);
    opacity:0; transition:opacity .2s; pointer-events:none; }
  .ana-toast.show { opacity:1; }
  /* 全文连续朗读：当前句用 accent 绿与荧光黄重点区分；块级描边、原文模式浅绿底 */
  .sa.reading .sa-en { box-shadow:0 0 0 2px var(--accent); border-radius:4px; }
  article.ana-off .sa.reading .sa-en { background:var(--p-bg); color:var(--p-fg);
    border-radius:3px; padding:1px 5px; box-shadow:0 0 0 1.5px var(--accent); }
  .sa { scroll-margin-top:76px; }
  /* 只看原文：无编号、无竖线、无底色，同段句子连续排版，字号恢复正文大小 */
  article.ana-off .sa.sa-title-wrap { display:none; }
  article.ana-off .pgrp { margin:0 0 20px; }
  article.ana-off .sa { display:contents; }
  article.ana-off .sa-an { display:none; }
  article.ana-off .sa-en { display:inline; background:transparent; border:none;
    border-radius:0; padding:0; font-size:18px; line-height:1.9; box-shadow:none; color:var(--fg); }
  article.ana-off .sa-en .sn { display:none; }
  article.ana-off .sa-en .sa-play { display:none; }
  article.ana-off .sa-en::after { content:" "; }
  @media (max-width:920px) {
    .sa-en { font-size:16px; }
    article.ana-off .sa-en { font-size:17px; }
    article { max-width:720px; }
    .ana-toolbar .hint, .ana-toolbar kbd { display:none; }
  }
  /* 打印：白底黑字纯原文（终端配色不用于纸面） */
  @media print {
    #anaProg, .ana-toolbar, #anaTop, .ana-toast, .ana-gloss, .ana-orig { display:none !important; }
    html, body, article { background:#fff !important; color:#000 !important; }
    article { max-width:none !important; padding:0 !important; }
    h1.ana-dup { display:block !important; color:#000 !important; }
    .sa-title-wrap, .sa-an { display:none !important; }
    .pgrp { margin:0 0 12px !important; }
    .sa { display:contents !important; }
    .sa-en { display:inline !important; background:none !important; border:none !important;
      border-radius:0 !important; padding:0 !important; font-size:11.5pt !important;
      line-height:1.7 !important; color:#000 !important; box-shadow:none !important; }
    .sa-en .sn, .sa-en .sa-play { display:none !important; }
    .sa-en::after { content:" " !important; }
    .sa-en mark { background:none !important; color:#000 !important;
      box-shadow:none !important; padding:0 !important; }
    article figure { display:block !important; margin:0 0 16px !important; }
  }
"""

TOOLBAR = ('<div id="anaProg"><i></i></div>'
           '<div class="ana-toolbar">'
           '<button id="toggleAn" type="button">隐藏分析（只看原文）</button>'
           '<button id="playAll" type="button" title="从标题开始连续朗读英文全文（再点一次停止）">▶ 播放全文</button>'
           '<span class="hint">逐句精读：上为英文（黄色＝重点短语/结构），下为 译文 · 语法 · 短语'
           '　·　<kbd>A</kbd> 切换模式　·　点喇叭朗读整句　·　播放全文连续朗读　·　点句子序号复制原句'
           '　·　只看原文时按住 <kbd>Ctrl</kbd>（Mac 为 <kbd>Cmd</kbd>）点黄色短语，跳到本句分析</span>'
           '<span class="tts-cfg">'
           '<label class="tts-item">语音<select id="anaVoice" title="朗读语音">'
           '<option value="">自动（英语）</option></select></label>'
           '<label class="tts-item">语速<select id="anaRate" title="朗读语速">'
           '<option value="0.7">0.7× 慢</option>'
           '<option value="0.85">0.85×</option>'
           '<option value="0.95" selected>0.95×</option>'
           '<option value="1">1× 正常</option>'
           '<option value="1.15">1.15×</option>'
           '<option value="1.3">1.3× 快</option>'
           '</select></label></span></div>')
TOP_BUTTON = ('<button id="anaTop" type="button" title="回到顶部" aria-label="回到顶部">↑</button>'
              '<div class="ana-toast" id="anaToast"></div>')
TOGGLE_JS = """<script>(function(){
  var art = document.querySelector('article'),
      btn = document.getElementById('toggleAn'),
      prog = document.querySelector('#anaProg i'),
      topBtn = document.getElementById('anaTop'),
      toast = document.getElementById('anaToast'),
      KEY = 'as:mode:' + location.pathname;
  function sync() {
    var off = art.classList.contains('ana-off');
    btn.textContent = off ? '显示分析' : '隐藏分析（只看原文）';
  }
  try { if (localStorage.getItem(KEY) === 'off') art.classList.add('ana-off'); } catch (e) {}
  sync();
  function toggle() {
    art.classList.toggle('ana-off');
    try { localStorage.setItem(KEY, art.classList.contains('ana-off') ? 'off' : 'on'); } catch (e) {}
    stopSpeak();
    sync();
  }
  btn.addEventListener('click', toggle);
  document.addEventListener('keydown', function (e) {
    var t = e.target.tagName;
    if ((e.key === 'a' || e.key === 'A') && t !== 'INPUT' && t !== 'TEXTAREA') toggle();
  });
  function onScroll() {
    var h = document.documentElement;
    var max = h.scrollHeight - h.clientHeight;
    prog.style.width = (max > 0 ? (h.scrollTop || document.body.scrollTop) / max * 100 : 0) + '%';
    topBtn.classList.toggle('show', (h.scrollTop || document.body.scrollTop) > 500);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
  topBtn.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
  var toastTimer;
  function showToast(msg) {
    toast.textContent = msg; toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove('show'); }, 1400);
  }
  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { showToast('已复制原句'); },
        function () { fallbackCopy(text); });
    } else fallbackCopy(text);
  }
  function fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); showToast('已复制原句'); } catch (e) {}
    document.body.removeChild(ta);
  }
  /* 句末朗读：Web Speech API；工具栏可选英语语音与语速，按页记忆 */
  var curPlay = null, curText = '';
  var voiceSel = document.getElementById('anaVoice'),
      rateSel = document.getElementById('anaRate'),
      playAllBtn = document.getElementById('playAll');
  /* 全文连续朗读状态：els 为按 DOM 顺序的全部句子，token 使旧回调失效 */
  var full = { active:false, els:[], i:0, token:0, timer:null };
  var VOICE_KEY = 'as:voice:' + location.pathname,
      RATE_KEY = 'as:rate:' + location.pathname;
  var savedVoice = '', savedRate = '';
  try {
    savedVoice = localStorage.getItem(VOICE_KEY) || '';
    savedRate = localStorage.getItem(RATE_KEY) || '';
  } catch (e) {}
  if (savedRate && rateSel) rateSel.value = savedRate;
  function englishVoices() {
    if (!('speechSynthesis' in window)) return [];
    var list = window.speechSynthesis.getVoices() || [], out = [], seen = {}, v, i, key;
    for (i = 0; i < list.length; i++) {
      v = list[i];
      if (/^en(-|_|$)/i.test(v.lang || '')) {
        key = v.voiceURI || (v.name + '|' + v.lang);
        if (!seen[key]) { seen[key] = 1; out.push(v); }
      }
    }
    return out;
  }
  function fillVoices() {
    if (!voiceSel) return;
    var voices = englishVoices(), i, opt;
    while (voiceSel.options.length > 1) voiceSel.remove(voiceSel.options.length - 1);
    for (i = 0; i < voices.length; i++) {
      opt = document.createElement('option');
      opt.value = voices[i].voiceURI || voices[i].name;
      opt.textContent = voices[i].name + ' (' + voices[i].lang + ')';
      voiceSel.appendChild(opt);
    }
    voiceSel.value = savedVoice;
    if (voiceSel.selectedIndex < 0) voiceSel.value = '';
  }
  function chosenVoice() {
    if (!voiceSel) return null;
    var want = voiceSel.value, voices = englishVoices(), i;
    if (want) {
      for (i = 0; i < voices.length; i++)
        if ((voices[i].voiceURI || voices[i].name) === want) return voices[i];
      return null;
    }
    for (i = 0; i < voices.length; i++)
      if (/^en-US$/i.test(voices[i].lang)) return voices[i];
    return voices[0] || null;
  }
  function stopSpeak() {
    stopFull();
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    if (curPlay) { curPlay.classList.remove('playing'); curPlay = null; }
    curText = '';
  }
  function speakText(btn, text) {
    if (!('speechSynthesis' in window)) { showToast('当前浏览器不支持语音朗读'); return; }
    if (!text) return;
    stopSpeak();
    var u = new SpeechSynthesisUtterance(text);
    u.lang = 'en-US';
    u.rate = parseFloat(rateSel && rateSel.value) || 0.95;
    var voice = chosenVoice();
    if (voice) u.voice = voice;
    curPlay = btn; curText = text;
    btn.classList.add('playing');
    u.onend = u.onerror = function () {
      btn.classList.remove('playing');
      if (curPlay === btn) { curPlay = null; curText = ''; }
    };
    window.speechSynthesis.speak(u);
  }
  function speakSentence(btn) {
    if (curPlay === btn) { stopSpeak(); return; }
    var row = btn.closest('.sa');
    speakText(btn, row ? row.getAttribute('data-en') || '' : '');
  }
  /* 全文连续朗读：逐句调度，当前句高亮并平滑跟随滚动 */
  function readables() {
    return Array.prototype.slice.call(art.querySelectorAll('.sa[data-en]'));
  }
  function clearReading() {
    var el = art.querySelector('.sa.reading');
    if (el) el.classList.remove('reading');
  }
  function setFullUI(on) {
    if (playAllBtn) {
      playAllBtn.textContent = on ? '■ 停止播放' : '▶ 播放全文';
      playAllBtn.classList.toggle('playing', !!on);
    }
  }
  function clearFullTimer() {
    if (full.timer) { clearInterval(full.timer); full.timer = null; }
  }
  function endFull() {
    full.active = false;
    full.token++;
    clearFullTimer();
    clearReading();
    setFullUI(false);
  }
  function stopFull() {
    if (!full.active) { clearFullTimer(); clearReading(); setFullUI(false); return; }
    endFull();
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
  }
  function speakOne() {
    var token = full.token, el = full.els[full.i];
    if (!el) { endFull(); return; }
    clearReading();
    el.classList.add('reading');
    /* ana-off 模式下 .sa 为 display:contents，自身无盒子，须滚动内部 .sa-en */
    var box = el.querySelector('.sa-en');
    if (box && box.offsetParent !== null) box.scrollIntoView({ behavior:'smooth', block:'center' });
    var u = new SpeechSynthesisUtterance(el.getAttribute('data-en') || '');
    u.lang = 'en-US';
    u.rate = parseFloat(rateSel && rateSel.value) || 0.95;
    var voice = chosenVoice();
    if (voice) u.voice = voice;
    u.onend = u.onerror = function () {
      if (full.active && token === full.token) {
        full.i++;
        if (full.i < full.els.length) { full.token++; speakOne(); }
        else endFull();
      }
    };
    window.speechSynthesis.speak(u);
  }
  function startFull() {
    if (!('speechSynthesis' in window)) { showToast('当前浏览器不支持语音朗读'); return; }
    stopSpeak();
    full.els = readables();
    if (!full.els.length) return;
    full.i = 0;
    full.active = true;
    full.token++;
    setFullUI(true);
    /* Chrome 长文朗读约 15 秒后可能被挂起，定时 resume 兜底 */
    clearFullTimer();
    full.timer = setInterval(function () {
      try { if (full.active) window.speechSynthesis.resume(); } catch (e) {}
    }, 10000);
    speakOne();
  }
  function restartFullSentence() {
    if (!full.active) return;
    full.token++;
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    speakOne();
  }
  if (playAllBtn) playAllBtn.addEventListener('click', function () {
    if (full.active) stopFull(); else startFull();
  });
  if (voiceSel && 'speechSynthesis' in window) {
    fillVoices();
    window.speechSynthesis.onvoiceschanged = fillVoices;
    voiceSel.addEventListener('change', function () {
      try { localStorage.setItem(VOICE_KEY, voiceSel.value); } catch (e) {}
      if (curPlay && curText) speakText(curPlay, curText);
      else restartFullSentence();
    });
  } else if (voiceSel) {
    voiceSel.disabled = true;
    if (rateSel) rateSel.disabled = true;
    if (playAllBtn) playAllBtn.disabled = true;
  }
  if (rateSel) rateSel.addEventListener('change', function () {
    try { localStorage.setItem(RATE_KEY, rateSel.value); } catch (e) {}
    if (curPlay && curText) speakText(curPlay, curText);
    else restartFullSentence();
  });
  document.addEventListener('click', function (e) {
    /* 只看原文模式：按住 Ctrl/⌘ 点黄色短语，切回分析并定位到本句 */
    if (art.classList.contains('ana-off') && (e.ctrlKey || e.metaKey)) {
      var mk = e.target.closest ? e.target.closest('.sa-en mark') : null;
      if (mk) {
        var row = mk.closest('.sa');
        e.preventDefault();
        art.classList.remove('ana-off');
        try { localStorage.setItem(KEY, 'on'); } catch (err) {}
        stopSpeak(); sync();
        if (row) {
          row.scrollIntoView({ block: 'center' });
          row.classList.add('sa-flash');
          setTimeout(function () { row.classList.remove('sa-flash'); }, 1800);
        }
        return;
      }
    }
    var play = e.target.closest ? e.target.closest('.sa-play') : null;
    if (play) { speakSentence(play); return; }
    if (e.target.classList.contains('sn')) {
      var row = e.target.closest('.sa');
      if (row && row.getAttribute('data-en')) copyText(row.getAttribute('data-en'));
    }
  });
})();</script>"""


def _norm(s):
    return (s.replace("’", "'").replace("“", '"').replace("”", '"').replace(" ", " "))


def _nosp(s):
    return re.sub(r"\s+", "", _norm(s))


def _esc(s):
    return ihtml.escape(s, quote=False)


# ---------- 启发式英文断句（供 skeleton 预填，inject 仍逐字校验） ----------
# 句点前不表示句子结束的词（内部可含点：e.g. / U.S. / ph.d.）
SENT_ABBR = {
    # 称谓 / 头衔
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "mt", "rev",
    "hon", "pres", "gen", "rep", "sen", "sgt", "capt", "lt", "col",
    "messrs", "mlle", "mdme",
    # 常见缩写 / 拉丁词
    "etc", "vs", "viz", "cf", "ca", "ed", "eds", "pp", "vol", "no",
    "nos", "inc", "ltd", "co", "corp", "assn", "dept", "est", "fig",
    "eq", "al", "approx", "appt", "govt", "univ",
    "e.g", "i.e", "a.m", "p.m", "u.s", "u.k", "e.u", "n.y", "l.a",
    "ph.d", "b.a", "m.a", "b.s", "m.s",
    # 月份 / 星期
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept",
    "oct", "nov", "dec",
    "mon", "tue", "wed", "thu", "fri", "sat", "sun",
}
_CLOSING_QUOTES = "\"'”’)]"
_SENT_START = "\"'“‘(["


def split_sentences(text):
    """在 .!? （可后跟闭引号/括号）+ 空白 + 句首字符处断句。
    缩写、小数、人名首字母、省略号处不断；返回 strip 后的句子列表。"""
    out, start, n = [], 0, len(text)
    i = 0
    while i < n:
        c = text[i]
        if c not in ".!?":
            i += 1
            continue
        if c == "." and text[i:i + 3] == "...":
            i += 3
            continue
        if c == ".":
            j = i
            while j > start and (text[j - 1].isalnum() or text[j - 1] == "."):
                j -= 1
            token = text[j:i]
            k = i + 1
            if token[:1].isdigit() and k < n and text[k].isdigit():
                i += 1
                continue  # 小数
            if token.lower().rstrip(".") in SENT_ABBR:
                i += 1
                continue  # 缩写
            if re.fullmatch(r"[A-Z]", token) and re.match(r"\s+[\"'“”‘’]?[A-Z]", text[k:k + 4]):
                i += 1
                continue  # 人名首字母（George W. Bush）
        k = i + 1
        while k < n and text[k] in _CLOSING_QUOTES:
            k += 1
        m = re.match(r"\s+", text[k:]) if k < n else None
        if m:
            after = k + m.end()
            if after < n and (text[after].isupper() or text[after].isdigit()
                              or text[after] in _SENT_START):
                sent = text[start:k].strip()
                if sent:
                    out.append(sent)
                start = after
                i = after
                continue
        i += 1
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


def body_paragraphs(doc):
    """返回 article 内正文 <p> 的 (start, end, raw_inner, whole_tag)，跳过 meta/source。"""
    art0 = doc.index("<article>")
    out = []
    for m in re.finditer(r"<p(?:\s[^>]*)?>.*?</p>", doc[art0:], re.S):
        tag = m.group(0)
        if 'class="meta"' in tag or 'class="source"' in tag:
            continue
        inner = re.match(r"<p[^>]*>(.*)</p>", tag, re.S).group(1)
        out.append((m.start() + art0, m.end() + art0, inner, tag))
    return out


def render_gr(gr):
    return re.sub(r"｛(.+?)｝", r'<mark class="g">\1</mark>', _esc(gr))


def render_en(raw, span, hls):
    """raw: 段落原文; span: 句子字符区间(a,b); 在区间内把 hls 包上 mark。"""
    a, b = span
    # 建立 段落无空白字符序列 -> raw 位置 的映射
    flat = []
    for i, ch in enumerate(raw):
        if not ch.isspace():
            flat.append((len(flat), i, _norm(ch)))
    base_lo = next(k for k, (f, i, c) in enumerate(flat) if i == a)
    base_hi = next(k for k in reversed(range(len(flat))) if flat[k][1] == b)
    intervals = []
    seg_flat = "".join(c for _, _, c in flat[base_lo:base_hi + 1])
    for h in hls:
        needle = _nosp(h)
        start, hits = 0, 0
        while True:
            j = seg_flat.find(needle, start)
            if j < 0:
                break
            hits += 1
            intervals.append((flat[base_lo + j][1], flat[base_lo + j + len(needle) - 1][1]))
            start = j + len(needle)
        if hits == 0:
            raise ValueError(f"高亮短语在句中找不到: {h!r} || {raw[a:b+1][:80]}")
    intervals.sort(key=lambda x: x[0])
    out, cur = [], a
    for x, y in intervals:
        if x < cur:
            continue
        out.append(_esc(raw[cur:x]))
        out.append('<mark title="只看原文模式下按住 Ctrl（Mac 为 Cmd）点击，跳到本句分析">'
                   + _esc(raw[x:y + 1]) + "</mark>")
        cur = y + 1
    out.append(_esc(raw[cur:b + 1]))
    return "".join(out)


def _ph_html(phs):
    if not phs:
        return ""
    lis = "".join(f'<li><mark class="p">{_esc(p)}</mark> — {_esc(m)}</li>' for p, m in phs)
    return f'<div class="an-ph"><span class="lab lab-ph">短语</span><ul>{lis}</ul></div>'


SPEAKER_SVG = ('<svg viewBox="0 0 24 24" aria-hidden="true">'
               '<path d="M3 9.5v5h4l5 4.5v-14L7 9.5H3z" fill="currentColor"/>'
               '<path d="M16.5 9a4.5 4.5 0 0 1 0 6" fill="none" stroke="currentColor" '
               'stroke-width="1.8" stroke-linecap="round"/></svg>')


def build_cell(s, idx, en_html, title=False):
    cls = "sa-en sa-en-title" if title else "sa-en"
    badge = "" if title else (
        f'<span class="sn" title="点击复制原句">{idx}</span>')
    play = "" if title else (
        '<button type="button" class="sa-play" title="朗读整句（再点一次停止）" '
        f'aria-label="朗读整句">{SPEAKER_SVG}</button>')
    left = f'<div class="{cls}">{badge}{en_html}{play}</div>'
    data = f' data-en="{ihtml.escape(s["en"], quote=True)}"'
    right = ('<div class="sa-an">'
             f'<div class="an-zh"><span class="lab lab-zh">译</span>{_esc(s["zh"])}</div>'
             f'<div class="an-gr"><span class="lab lab-gr">语法</span>{render_gr(s["gr"])}</div>'
             + _ph_html(s.get("ph", [])) +
             '</div>')
    return f'<div class="sa"{data}>{left}{right}</div>'


def orig_link(url):
    if not url:
        return ""
    href = ihtml.escape(ihtml.unescape(url), quote=True)
    return (f' <a class="ana-orig" href="{href}" target="_blank" rel="noopener" '
            'title="在新标签页打开原网页">原文↗</a>')


def title_block(t, url=""):
    te = _esc(t["en"])
    for h in t.get("hl", []):
        if _esc(h) not in te:
            raise ValueError(f"标题高亮短语找不到: {h!r}")
        te = te.replace(_esc(h), "<mark>" + _esc(h) + "</mark>", 1)
    data_te = f' data-en="{ihtml.escape(t["en"], quote=True)}"'
    return (f'<div class="sa sa-title-wrap"{data_te}><div class="sa-en sa-en-title">' + te
            + orig_link(url) + '</div><div class="sa-an">'
            f'<div class="an-zh"><span class="lab lab-zh">译</span>{_esc(t["zh"])}</div>'
            f'<div class="an-gr"><span class="lab lab-gr">语法</span>{render_gr(t["gr"])}</div>'
            + _ph_html(t.get("ph", [])) +
            '</div></div>')


def glossary_block(data):
    """汇总标题与全部句子的短语，按短语文本去重（保留首次释义与出现顺序）。"""
    seen, items = set(), []
    sources = ([data["title"]] if data.get("title") else []) + [
        s for group in data.get("paragraphs", []) for s in group]
    for item in sources:
        for p, m in item.get("ph", []):
            key = p.strip().lower()
            if key and key not in seen:
                seen.add(key)
                items.append((p, m))
    if not items:
        return ""
    rows = "".join(f'<div class="gl-item"><mark class="p">{_esc(p)}</mark><span>{_esc(m)}</span></div>'
                   for p, m in items)
    return (f'<div class="ana-gloss"><h2>重点短语词汇表（{len(items)}）</h2>'
            f'<div class="gl-list">{rows}</div></div>')


def validate_analysis(paras, groups):
    """渲染前的纯文本校验，收集全部错误一次性抛出（避免一轮只报一个 hl）。"""
    errors = []
    if len(paras) != len(groups):
        raise ValueError(f"段落数不符: HTML 正文 {len(paras)} 段，JSON {len(groups)} 组")
    for gi, sentences in enumerate(groups):
        if not sentences:
            errors.append(f"第 {gi+1} 段没有任何句子")
            continue
        for si, s in enumerate(sentences):
            for key in ("en", "zh", "gr"):
                if not isinstance(s.get(key), str) or not s[key].strip():
                    errors.append(f"第 {gi+1} 段第 {si+1} 句缺少字段 {key}")
            if not isinstance(s.get("ph"), list):
                errors.append(f"第 {gi+1} 段第 {si+1} 句 ph 必须是 [短语, 释义] 列表")
    for pi, ((_, _, raw, _), sentences) in enumerate(zip(paras, groups), 1):
        flat_par = _nosp(raw)
        ptr = 0
        for s in sentences:
            f = _nosp(s.get("en", ""))
            if not f:
                continue
            j = flat_par.find(f, ptr)
            if j < 0:
                errors.append(f"第 {pi} 段中找不到句子: {s.get('en', '')[:60]}")
                break
            if j != ptr:
                errors.append(f"第 {pi} 段句子间存在未覆盖文本: …{flat_par[ptr:j][:40]} || {s['en'][:40]}")
            seg = flat_par[j:j + len(f)]
            for h in s.get("hl", []):
                if _nosp(h) not in seg:
                    errors.append(f"第 {pi} 段高亮找不到: {h!r} || {s.get('en', '')[:80]}")
            ptr = j + len(f)
        else:
            if ptr != len(flat_par):
                errors.append(f"第 {pi} 段尾部有未覆盖文本: {flat_par[ptr:][:60]}")
    if errors:
        head = f"发现 {len(errors)} 个问题:"
        raise ValueError(head + "\n  - " + "\n  - ".join(errors))


def inject_analysis(doc, data):
    if "</style>" not in doc:
        raise ValueError("HTML 中没有 <style> 块，无法注入样式")
    doc = doc.replace("</style>", ANALYSIS_CSS + "\n</style>", 1)
    paras = body_paragraphs(doc)
    groups = data.get("paragraphs", [])
    validate_analysis(paras, groups)

    replacements, counter = [], 0
    for pi, ((st, en, raw, _), sentences) in enumerate(zip(paras, groups), 1):
        flat_par = _nosp(raw)
        flat_items = [(i, _norm(ch)) for i, ch in enumerate(raw) if not ch.isspace()]
        blocks, ptr = [], 0
        for s in sentences:
            f = _nosp(s["en"])
            j = flat_par.find(f, ptr)
            if j < 0:
                raise ValueError(f"第 {pi} 段中找不到句子: {s['en'][:60]}")
            if j != ptr:
                raise ValueError(f"第 {pi} 段句子间存在未覆盖文本: …{flat_par[ptr:j][:40]} || {s['en'][:40]}")
            a = flat_items[j][0]
            b = flat_items[j + len(f) - 1][0]
            counter += 1
            blocks.append(build_cell(s, counter, render_en(raw, (a, b), s.get("hl", []))))
            ptr = j + len(f)
        if ptr != len(flat_par):
            raise ValueError(f"第 {pi} 段尾部有未覆盖文本: {flat_par[ptr:][:60]}")
        replacements.append((st, en, '<div class="pgrp">' + "".join(blocks) + "</div>"))

    out = doc
    for st, en, new in reversed(replacements):
        out = out[:st] + new + out[en:]
    if "</h1>" not in out:
        raise ValueError("HTML 中没有 <h1>，无法放置工具栏")
    src_m = re.search(r'<p class="source">Source: <a href="([^"]+)"', out)
    src_url = ihtml.unescape(src_m.group(1)) if src_m else ""
    has_title = bool(data.get("title"))
    if has_title:
        out = out.replace("<h1>", '<h1 class="ana-dup">', 1)  # 分析模式隐藏，避免与标题分析块重复
    if src_url:  # 原 h1 标题后挂“原文”标签（纯原文模式可见）
        out = out.replace("</h1>", orig_link(src_url) + "</h1>", 1)
    # 日期 meta 挪到工具栏正下方（原位置在标题块之后，显得割裂）
    meta_m = re.search(r'<p class="meta">.*?</p>', out, re.S)
    meta_html = meta_m.group(0) if meta_m else ""
    if meta_m:
        out = out[:meta_m.start()] + out[meta_m.end():]
    insert = TOOLBAR + meta_html
    if has_title:
        insert += title_block(data["title"], src_url)
    out = out.replace("</h1>", "</h1>" + insert, 1)
    gloss = glossary_block(data)
    if gloss:
        if '<p class="source">' in out:
            out = out.replace('<p class="source">', gloss + '\n  <p class="source">', 1)
        else:
            out = out.replace("</article>", gloss + "\n</article>", 1)
    out = out.replace("</article>", TOP_BUTTON + TOGGLE_JS + "\n</article>", 1)
    return out, counter


# ---------- 已注入检测 / 原件备份 ----------
def is_injected(doc):
    return 'class="ana-toolbar"' in doc or "sa-en" in doc


def pristine_path(path):
    stem, ext = os.path.splitext(path)
    return stem + ".orig" + (ext or ".html")


def load_source(html):
    """读取待注入的源 HTML；若已被注入且存在 .orig.html 备份，自动改用备份。"""
    doc = open(html, encoding="utf-8").read()
    backup = pristine_path(html)
    if is_injected(doc):
        if not os.path.exists(backup):
            raise ValueError("该 HTML 已注入过分析，且找不到 .orig.html 备份，请从抓取产物重新开始")
        doc = open(backup, encoding="utf-8").read()
        if is_injected(doc):
            raise ValueError(f"备份 {backup} 本身也已被注入，请从抓取产物重新开始")
        print(f"检测到已注入的 HTML，自动改用备份原件: {backup}", file=sys.stderr)
        return doc, backup
    return doc, html


def require_pristine_paragraphs(doc):
    if is_injected(doc):
        raise ValueError("该 HTML 已注入过分析；请改对 .orig.html 备份原件运行本命令，或重新抓取")
    paras = body_paragraphs(doc)
    if not paras:
        raise ValueError("未找到正文 <p> 段落，确认传入的是 fetch 产出的原始 HTML")
    return paras


def cmd_inject(args):
    doc, src_path = load_source(args.html)
    backup = pristine_path(args.html)
    data = json.load(open(args.json, encoding="utf-8"))
    out, n = inject_analysis(doc, data)
    dest = args.output or args.html  # 默认就地改写
    if os.path.abspath(dest) == os.path.abspath(src_path) and src_path.endswith(".orig.html"):
        raise ValueError("拒绝就地注入 .orig.html 备份原件；请对正文 HTML 运行 inject，或用 -o 另存")
    if os.path.abspath(dest) == os.path.abspath(src_path) and not os.path.exists(backup):
        shutil.copyfile(src_path, backup)
        print(f"已备份原件: {backup}（此后重复 inject 会自动以它为源）", file=sys.stderr)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(out)
    extra = "（含标题块）" if data.get("title") else ""
    print(f"OK: 注入 {n} 个句子分析块{extra} -> {dest}")


def cmd_check(args):
    doc, _ = load_source(args.html)
    data = json.load(open(args.json, encoding="utf-8"))
    _, n = inject_analysis(doc, data)
    extra = "（含标题块）" if data.get("title") else ""
    print(f"OK: 校验通过，{n} 个句子分析块{extra}，未写入任何文件")


def cmd_paragraphs(args):
    doc = open(args.html, encoding="utf-8").read()
    paras = require_pristine_paragraphs(doc)
    rows = [{"i": i, "text": raw} for i, (_, _, raw, _) in enumerate(paras)]
    print(json.dumps(rows, ensure_ascii=False, indent=2))


ENTITY_RE = re.compile(r"&(?:#x?[0-9a-f]+|[a-z][a-z0-9]+);", re.I)
# 只用于正文的结构性字符（等价于浏览器解码后的文本）；&amp;/&lt;/&gt;/&quot;/&nbsp; 也算
def scan_entities(paras):
    """返回 [(段号, 实体, 上下文)]，供实体体检；正文 <p> 里出现实体意味着注入后会双重转义。"""
    hits = []
    for i, (_, _, raw, _) in enumerate(paras):
        for m in ENTITY_RE.finditer(raw):
            ctx = re.sub(r"\s+", " ", raw[max(0, m.start() - 25):m.end() + 25]).strip()
            hits.append((i, m.group(0), ctx))
    return hits


def normalize_html_entities(html_path):
    """把正文 <p> 内的 HTML 实体解码为真字符并就地重写源 HTML，返回替换处数。

    必须在 skeleton 之前做：注入时 en 会再被 html-escape，源文若留着 &#x27;，
    精读块里会原样显示成字面文本（check 拦不住）。"""
    doc = open(html_path, encoding="utf-8").read()
    paras = require_pristine_paragraphs(doc)
    total, repls = 0, []
    for st, en, raw, _ in paras:
        if ENTITY_RE.search(raw):
            total += len(ENTITY_RE.findall(raw))
            repls.append((st, en, ihtml.unescape(raw)))
    if not repls:
        return 0
    for st, en, new_inner in reversed(repls):
        old_tag = doc[st:en]
        new_tag = re.sub(r"(<p(?:\s[^>]*)?>).*(</p>)", lambda m: m.group(1) + new_inner + m.group(2),
                         old_tag, flags=re.S)
        doc = doc[:st] + new_tag + doc[en:]
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return total


def skeleton_data(doc):
    paras = require_pristine_paragraphs(doc)
    h1m = re.search(r"<h1[^>]*>(.*?)</h1>", doc, re.S)
    h1 = ihtml.unescape(re.sub(r"<[^>]+>", "", h1m.group(1)).strip()) if h1m else ""
    groups, fallback = [], 0
    for _, _, raw, _ in paras:
        sents = split_sentences(raw)
        if "".join(_nosp(s) for s in sents) != _nosp(raw):
            sents, fallback = [raw], fallback + 1  # 断句意外丢字时保守回退整段
        groups.append([{"en": s, "hl": [], "zh": "", "gr": "", "ph": []} for s in sents])
    skel = {"title": {"en": h1, "hl": [], "zh": "", "gr": "", "ph": []},
            "paragraphs": groups}
    return skel, fallback


def cmd_skeleton(args):
    if args.normalize:
        n = normalize_html_entities(args.html)
        if n:
            print(f"已在源 HTML 正文解码 {n} 处 HTML 实体: {args.html}", file=sys.stderr)
    doc = open(args.html, encoding="utf-8").read()
    paras = require_pristine_paragraphs(doc)
    hits = scan_entities(paras)
    if hits:
        kinds = {}
        for _, e, _ in hits:
            kinds[e] = kinds.get(e, 0) + 1
        sample = hits[0]
        print("⚠ 正文检测到 HTML 实体（注入后精读块会原样显示字面实体）："
              + ", ".join(f"{e}×{c}" for e, c in list(kinds.items())[:6]), file=sys.stderr)
        print(f"  首次出现于第 {sample[0] + 1} 段: …{sample[2]}…", file=sys.stderr)
        print("  修复：重跑 skeleton 并加 --normalize（会就地解码源 HTML 正文）", file=sys.stderr)
    skel, fallback = skeleton_data(doc)
    groups = skel["paragraphs"]
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(skel, f, ensure_ascii=False, indent=2)
    n_sent = sum(len(g) for g in groups)
    msg = f"OK: 骨架已写入 {args.output}（标题 1 + 段落 {len(groups)} / 自动断句 {n_sent} 条）"
    if fallback:
        msg += f"；{fallback} 段未能自动断句，已保留整段需手动拆分"
    msg += "；可用 draft 生成待填模板，或直接核对断句后填写 zh/gr/ph/hl"
    print(msg, file=sys.stderr)


# ---------- 一键截图自查 ----------
def find_chrome():
    candidates = [
        os.environ.get("CHROME"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        shutil.which("google-chrome"), shutil.which("chromium"),
        shutil.which("chrome"), shutil.which("microsoft-edge"),
    ]
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


# ---------- 极简 CDP 客户端（仅标准库；全页截图 / 深色模拟 / 页面度量） ----------
import socket as _socket
import struct as _struct
import tempfile as _tempfile
import time as _time


class _WS:
    def __init__(self, url, timeout=20):
        m = re.match(r"ws://([^/:]+)(?::(\d+))?(/.*)?", url)
        if not m:
            raise ValueError(f"无法解析 websocket 地址: {url}")
        host, port, path = m.group(1), int(m.group(2) or 80), m.group(3) or "/"
        self.sock = _socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        self.buf = b""
        while b"\r\n\r\n" not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("CDP 握手时连接关闭")
            self.buf += chunk
        head, self.buf = self.buf.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise ConnectionError("CDP websocket 握手失败")

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("CDP 连接已关闭")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send_text(self, text):
        payload = text.encode("utf-8")
        mask = os.urandom(4)
        frame = bytearray([0x81])
        n = len(payload)
        if n < 126:
            frame.append(0x80 | n)
        elif n < 65536:
            frame.append(0x80 | 126)
            frame += _struct.pack(">H", n)
        else:
            frame.append(0x80 | 127)
            frame += _struct.pack(">Q", n)
        frame += mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(frame))

    def _frame(self):
        b0, b1 = self._read(2)
        ln = b1 & 0x7F
        if ln == 126:
            ln = _struct.unpack(">H", self._read(2))[0]
        elif ln == 127:
            ln = _struct.unpack(">Q", self._read(8))[0]
        payload = self._read(ln) if ln else b""
        opcode = b0 & 0x0F
        fin = bool(b0 & 0x80)
        if opcode == 0x8:
            raise ConnectionError("CDP 对端关闭了 websocket")
        if opcode == 0x9:  # ping -> pong
            mask = os.urandom(4)
            self.sock.sendall(bytes([0x8A, 0x80 | ln]) + mask
                              + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))
            return self._frame()
        return fin, opcode, payload

    def recv_message(self):
        chunks = []
        while True:
            fin, _, payload = self._frame()
            chunks.append(payload)
            if fin:
                return b"".join(chunks).decode("utf-8", "replace")

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class CDP:
    """一个 headless Chrome 进程上的扁平会话 CDP 客户端。"""

    def __init__(self, timeout=25):
        chrome = find_chrome()
        if not chrome:
            raise ValueError("找不到 Chrome/Chromium/Edge，可用环境变量 CHROME 指定浏览器可执行文件路径")
        self.profile = _tempfile.mkdtemp(prefix="chrome-cdp-")
        self.errlog = os.path.join(self.profile, "cdp.log")
        logf = open(self.errlog, "wb")
        self.proc = subprocess.Popen(
            [chrome, "--headless=new", "--disable-gpu", "--no-first-run",
             "--hide-scrollbars", "--force-device-scale-factor=1",
             "--remote-debugging-port=0", f"--user-data-dir={self.profile}",
             "--no-proxy-server", "about:blank"],
            stderr=logf, stdout=subprocess.DEVNULL)
        ws_url = None
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            try:
                txt = open(self.errlog, encoding="utf-8", errors="replace").read()
            except OSError:
                txt = ""
            m = re.search(r"DevTools listening on (ws://\S+)", txt)
            if m:
                ws_url = m.group(1)
                break
            if self.proc.poll() is not None:
                raise ConnectionError("Chrome 调试进程提前退出")
            _time.sleep(0.2)
        if not ws_url:
            self.close()
            raise ConnectionError("等不到 Chrome DevTools 端口")
        self.ws = _WS(ws_url)
        self._next_id = 0

    def cmd(self, method, params=None, sid=None, timeout=30):
        self._next_id += 1
        mid = self._next_id
        msg = {"id": mid, "method": method, "params": params or {}}
        if sid:
            msg["sessionId"] = sid
        self.ws.send_text(json.dumps(msg))
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            data = json.loads(self.ws.recv_message())
            if data.get("id") == mid:
                if "error" in data:
                    raise ValueError(f"CDP {method} 失败: {data['error']}")
                return data.get("result", {})
        raise TimeoutError(f"CDP {method} 超时")

    def open_page(self, uri, width=1300):
        tid = self.cmd("Target.createTarget", {"url": "about:blank"})["targetId"]
        sid = self.cmd("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        self.cmd("Page.enable", sid=sid)
        self.cmd("Runtime.enable", sid=sid)
        # 先固定视口宽度再导航，否则 headless 默认 800px 会让正文重排变高
        self.cmd("Emulation.setDeviceMetricsOverride",
                 {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False},
                 sid=sid)
        self.cmd("Page.navigate", {"url": uri}, sid=sid)
        deadline = _time.time() + 30
        while _time.time() < deadline:
            r = self.cmd("Runtime.evaluate",
                         {"expression": "document.readyState", "returnByValue": True}, sid=sid)
            if r.get("result", {}).get("value") == "complete":
                break
            _time.sleep(0.2)
        _time.sleep(0.6)  # 字体/布局稳定
        return sid

    def set_scheme(self, sid, dark):
        self.cmd("Emulation.setEmulatedMedia",
                 {"features": [{"name": "prefers-color-scheme",
                                "value": "dark" if dark else "light"}]}, sid=sid)

    def page_height(self, sid):
        m = self.cmd("Page.getLayoutMetrics", sid=sid)
        return int(m["cssContentSize"]["height"]) + 2

    def evaluate(self, sid, expr):
        r = self.cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True}, sid=sid)
        return r.get("result", {}).get("value")

    def clip(self, sid, path, x, y, width, height):
        r = self.cmd("Page.captureScreenshot", {
            "format": "png",
            "clip": {"x": x, "y": y, "width": width, "height": height, "scale": 1},
            "captureBeyondViewport": True}, sid=sid, timeout=60)
        with open(path, "wb") as f:
            f.write(base64.b64decode(r["data"]))

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
            except OSError:
                pass
        shutil.rmtree(self.profile, ignore_errors=True)


def cmd_shot(args):
    import pathlib
    src_html = os.path.abspath(args.html)
    doc = open(src_html, encoding="utf-8").read()
    if not is_injected(doc):
        print("⚠ 该 HTML 尚未注入分析，两张截图不会有区别", file=sys.stderr)
    outdir = os.path.abspath(args.outdir or os.path.dirname(src_html))
    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(src_html))[0]
    tmp_off = os.path.join(os.path.dirname(src_html), "." + stem + ".ana-off.html")
    with open(tmp_off, "w", encoding="utf-8") as f:
        f.write(doc.replace("<article>", '<article class="ana-off">', 1))
    part_dir = os.path.join(outdir, stem + ".parts")
    os.makedirs(part_dir, exist_ok=True)
    for old in os.listdir(part_dir):
        os.unlink(os.path.join(part_dir, old))
    names = {("on", False): stem + ".shot-on.png",
             ("on", True): stem + ".shot-on.dark.png",
             ("off", False): stem + ".shot-off.png",
             ("off", True): stem + ".shot-off.dark.png"}
    cdp = None
    try:
        cdp = CDP()
        for html_path, mode in ((src_html, "on"), (tmp_off, "off")):
            uri = pathlib.Path(html_path).as_uri()
            for dark in (False, True):
                sid = cdp.open_page(uri, args.width)
                cdp.set_scheme(sid, dark)
                height = args.height or cdp.page_height(sid)
                png = os.path.join(outdir, names[(mode, dark)])
                cdp.clip(sid, png, 0, 0, args.width, height)
                print(f"截图: {png}（高 {height}px，{'深色' if dark else '浅色'}）", file=sys.stderr)
                if not dark or mode == "on":
                    # 浅色：精读/原文都出全量分片；深色：只精读模式出首/中/尾
                    offsets = list(range(0, height, args.part))
                    if dark:
                        mid = offsets[len(offsets) // 2]
                        offsets = [offsets[0], mid, offsets[-1]]
                    for y in offsets:
                        h = min(args.part, height - y)
                        tag = {"on": "on", "off": "off"}[mode]
                        if dark:
                            tag += "-dark"
                        part = os.path.join(part_dir, f"{tag}-{y:05d}.png")
                        cdp.clip(sid, part, 0, y, args.width, h)
    finally:
        if cdp:
            cdp.close()
        if os.path.isfile(tmp_off):
            os.unlink(tmp_off)
    print(f"OK: 全页图（浅/深 × 精读/原文）已写入 {outdir}")
    print(f"OK: 可读分片（{args.part}px/片）在 {part_dir}，核对时只读分片，勿直接读万像素全页图")


def cmd_open(args):
    import pathlib
    import webbrowser
    path = os.path.abspath(args.html)
    if not os.path.isfile(path):
        raise ValueError(f"文件不存在: {path}")
    uri = pathlib.Path(path).as_uri()
    if not webbrowser.open_new_tab(uri):
        raise ValueError(f"无法调起系统浏览器，请手动打开: {path}")
    print(f"OK: 已在默认浏览器打开 {path}")


# ---------- draft DSL：助手只写中文，不照抄 en/JSON 样板 ----------
DRAFT_HELP = (
    "// 逐句精读 draft：每个 # 块填 zh/gr 两行；ph 下每条一行 `- 英文短语 | 中文释义`；\n"
    "// hl 行填 `高亮1 | 高亮2`，留空则自动取 ph 英文列。\n"
    "// > en 是只读原文。拆句：同段内再贴一组 `> en:`+zh/gr/ph/hl；\n"
    "// 合句：把两条 > en 接成一行、注释合并成一组。空行与 // 行被忽略。\n"
    "// 填完运行 fill 写回 analysis.json。\n"
)


def _draft_entry(en=""):
    return [f"> en: {en}", "zh: ", "gr: ", "ph:", "hl: "]


def cmd_draft(args):
    data = json.load(open(args.json, encoding="utf-8"))
    lines = [DRAFT_HELP.rstrip(), "", "# T"]
    t = data.get("title") or {}
    lines += _draft_entry(t.get("en", ""))
    for pi, group in enumerate(data.get("paragraphs", [])):
        for si, s in enumerate(group):
            lines += ["", f"# {pi}.{si}"] + _draft_entry(s["en"])
    with open(args.output, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    n = sum(len(g) for g in data.get("paragraphs", []))
    print(f"OK: draft 模板已写入 {args.output}（标题 + {n} 句）；直接在文件里填写，勿改动 # 编号",
          file=sys.stderr)


def parse_draft(text):
    """解析 draft 文本 → (title_entry_or_None, {pidx: [entry,...]})。

    entry = {"en","zh","gr","ph":[[e,z]...],"hl":[...]}；# 块内多个 > en 即拆句。"""
    blocks = {}
    cur_pid, title_entry, entry, mode = None, None, None, None

    def flush():
        nonlocal entry, mode, title_entry
        if entry is not None:
            if cur_pid == "T":
                if title_entry is not None:
                    raise ValueError("# T 标题块只允许一个 > en 条目")
                title_entry = entry
            else:
                blocks.setdefault(cur_pid, []).append(entry)
        entry, mode = None, None

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        m = re.match(r"#\s*(T|\d+)(?:\.(\d+))?\s*$", line)
        if m:
            flush()
            if m.group(1) == "T":
                if m.group(2) is not None:
                    raise ValueError("标题块头只能是 `# T`")
                cur_pid = "T"
            else:
                cur_pid = int(m.group(1))
            continue
        if line.startswith("> en:"):
            if cur_pid is None:
                raise ValueError(f"内容前缺少 # 块头，遇到: {line[:60]}")
            if entry is not None:
                if cur_pid == "T":
                    raise ValueError("# T 标题块只允许一个 > en 条目")
                blocks.setdefault(cur_pid, []).append(entry)
            entry = {"en": line[5:].strip(), "zh": "", "gr": "", "ph": [], "hl": []}
            mode = None
            continue
        if entry is None:
            raise ValueError(f"缺少 # 块头或 > en 起始行，遇到: {line[:60]}")
        if line.startswith("zh:"):
            entry["zh"] = line[3:].strip(); mode = None
        elif line.startswith("gr:"):
            entry["gr"] = line[3:].strip(); mode = None
        elif line.startswith("hl:"):
            entry["hl"] = [x.strip() for x in line[3:].split("|") if x.strip()]
            mode = None
        elif line.startswith("ph:"):
            rest = line[3:].strip()
            if rest:
                raise ValueError("ph: 单独成行，条目另起一行写 `- 英文 | 中文`")
            mode = "ph"
        elif mode == "ph":
            body = line[2:].strip() if line.startswith("-") else line
            if "|" not in body:
                raise ValueError(f"ph 条目必须是 `英文 | 中文` 形式: {line[:60]}")
            en_ph, zh_ph = body.split("|", 1)
            if not en_ph.strip() or not zh_ph.strip():
                raise ValueError(f"ph 条目缺英文或中文: {line[:60]}")
            entry["ph"].append([en_ph.strip(), zh_ph.strip()])
        else:
            raise ValueError(f"无法解析的行: {line[:60]}")
    flush()
    return title_entry, blocks


def cmd_fill(args):
    data = json.load(open(args.json, encoding="utf-8"))
    title_entry, blocks = parse_draft(open(args.draft, encoding="utf-8").read())
    n_paras = len(data.get("paragraphs", []))
    bad_pids = [p for p in blocks if not isinstance(p, int) or p < 0 or p >= n_paras]
    if bad_pids:
        raise ValueError(f"draft 出现越界段号: {bad_pids}（正文共 {n_paras} 段）")
    empties = []
    groups = []
    for pi in range(n_paras):
        entries = blocks.get(pi, [])
        if not entries:
            raise ValueError(f"第 {pi + 1} 段在 draft 中没有任何条目（整段被删了？）")
        for si, e in enumerate(entries):
            if not e["en"]:
                raise ValueError(f"第 {pi + 1} 段第 {si + 1} 条 en 为空")
            if not e["zh"]:
                empties.append(f"{pi}.{si} 缺 zh")
            if not e["gr"]:
                empties.append(f"{pi}.{si} 缺 gr")
            for k, pair in enumerate(e["ph"]):
                if len(pair) != 2:
                    empties.append(f"{pi}.{si} 第 {k + 1} 条 ph 不是二元组")
            if not e["hl"]:
                e["hl"] = [pair[0] for pair in e["ph"]]
        groups.append(entries)
    if empties:
        raise ValueError("draft 还有未填项：\n  " + "\n  ".join(empties[:20])
                         + (f"\n  …共 {len(empties)} 处" if len(empties) > 20 else ""))
    out = {"title": None, "paragraphs": groups}
    if title_entry:
        if not title_entry["zh"] or not title_entry["gr"]:
            raise ValueError("标题块缺 zh 或 gr（不需要标题分析可删掉整个 # T 块）")
        if not title_entry["hl"]:
            title_entry["hl"] = [pair[0] for pair in title_entry["ph"]]
        out["title"] = title_entry
    dest = args.output or args.json
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    n_sent = sum(len(g) for g in groups)
    print(f"OK: draft 已合并为 {n_sent} 句分析 -> {dest}；下一步 check 校验拼句覆盖", file=sys.stderr)


# ---------- verify：注入结果静态验收（不依赖肉眼） ----------


def cmd_verify(args):
    path = args.html
    doc = open(path, encoding="utf-8").read()
    if not is_injected(doc):
        raise ValueError("该 HTML 尚未注入分析，verify 针对注入后的成品")
    fails, warns, oks = [], [], []

    n_cells = doc.count('<div class="sa"')
    if n_cells:
        oks.append(f"精读句块 {n_cells} 个")
    else:
        fails.append("找不到任何精读句块（class=sa）")

    empty_zh = len(re.findall(r'<div class="an-zh"><span[^>]*>译</span>\s*</div>', doc))
    empty_gr = len(re.findall(r'<div class="an-gr"><span[^>]*>语法</span>\s*</div>', doc))
    if empty_zh:
        fails.append(f"{empty_zh} 句缺译文")
    if empty_gr:
        fails.append(f"{empty_gr} 句缺语法")
    if not empty_zh and not empty_gr:
        oks.append("每句 zh/gr 均非空")

    tofu = re.findall(r'<li><mark class="p">\s*(?:en|En|EN)\s*</mark>\s*[—-]\s*(?:zh|Zh|ZH)\s*</li>',
                      doc)
    if tofu:
        fails.append(f"{len(tofu)} 条短语渲染成 en — zh 豆腐块（ph 写成了 dict，须改二元数组）")
    else:
        oks.append("短语无 en — zh 豆腐块")

    dbl = doc.count("&amp;#")
    if dbl:
        fails.append(f"出现 {dbl} 处 &amp;#… 双重转义（源文 HTML 实体未归一，重跑 skeleton --normalize）")
    else:
        oks.append("无双重转义实体")

    gl = len(re.findall(r'class="gl-item"', doc))
    if gl:
        oks.append(f"词汇表 {gl} 条")
        if args.json:
            data = json.load(open(args.json, encoding="utf-8"))
            srcs = ([data["title"]] if data.get("title") else []) + \
                   [s for g in data.get("paragraphs", []) for s in g]
            seen = {p.strip().lower() for it in srcs for p, _ in it.get("ph", []) if p.strip()}
            if gl != len(seen):
                warns.append(f"词汇表 {gl} 条与 JSON 去重短语 {len(seen)} 条不一致")
    else:
        warns.append("没有词汇表（所有句 ph 均为空？）")

    if re.search(r'<p class="source">\s*Source:\s*<a href="https?://', doc):
        oks.append("文末 source 链接存在")
    else:
        fails.append("找不到文末 source 链接")

    print("== verify ==")
    for m in oks:
        print(f"  PASS  {m}")
    for m in warns:
        print(f"  WARN  {m}")
    for m in fails:
        print(f"  FAIL  {m}")
    try:
        import pathlib
        cdp = CDP()
        try:
            sid = cdp.open_page(pathlib.Path(os.path.abspath(path)).as_uri())
            h = cdp.page_height(sid)
            print(f"  INFO  精读页真实高度 {h}px（shot 已自动取全页；手动截图 -H 须 ≥ 此值）")
        finally:
            cdp.close()
    except Exception as e:
        print(f"  WARN  浏览器度量跳过: {e}")
    if fails:
        sys.exit(1)
    print("OK: 静态验收全部通过")


# ---------- prep：fetch + skeleton + 实体体检 + draft 一条龙 ----------
def cmd_prep(args):
    out_path = cmd_fetch(args)
    base = os.path.splitext(out_path)[0]
    analysis_path = os.path.join(os.path.dirname(base), "analysis.json")
    cmd_skeleton(argparse.Namespace(html=out_path, output=analysis_path,
                                    normalize=args.normalize))
    draft_path = base + ".draft.md"
    cmd_draft(argparse.Namespace(json=analysis_path, output=draft_path))
    print("", file=sys.stderr)
    print(f"下一步：填写 {draft_path}，然后运行", file=sys.stderr)
    print(f"  python3 article_study.py fill {draft_path} -j {analysis_path}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="文章抓取 + 逐句精读上下排版注入")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_fetch = sub.add_parser("fetch", help="抓取文章 URL 为单文件 HTML")
    p_fetch.add_argument("url")
    p_fetch.add_argument("-o", "--output", help="输出文件路径（与 -d 二选一）")
    p_fetch.add_argument("-d", "--dir", help="按文章标题建子目录：<dir>/<标题slug>/<标题slug>.html")
    p_fetch.set_defaults(func=cmd_fetch)

    p_par = sub.add_parser("paragraphs", help="打印 HTML 正文段落（JSON）")
    p_par.add_argument("html")
    p_par.set_defaults(func=cmd_paragraphs)

    p_prep = sub.add_parser("prep", help="一条龙：fetch + skeleton + 实体体检 + draft 模板")
    p_prep.add_argument("url")
    p_prep.add_argument("-o", "--output", help="HTML 输出路径（与 -d 二选一）")
    p_prep.add_argument("-d", "--dir", help="按文章标题建子目录：<dir>/<标题slug>/")
    p_prep.add_argument("--normalize", action="store_true", help="正文遇到 HTML 实体先就地解码")
    p_prep.set_defaults(func=cmd_prep)

    p_skel = sub.add_parser("skeleton", help="生成分析 JSON 骨架（自动按句拆分，附实体体检）")
    p_skel.add_argument("html")
    p_skel.add_argument("-o", "--output", required=True)
    p_skel.add_argument("--normalize", action="store_true",
                        help="把正文 <p> 里的 HTML 实体（如 &#x27;）就地解码后再出骨架")
    p_skel.set_defaults(func=cmd_skeleton)

    p_draft = sub.add_parser("draft", help="从骨架 JSON 生成待填 draft.md（助手只写中文）")
    p_draft.add_argument("-j", "--json", required=True)
    p_draft.add_argument("-o", "--output", required=True)
    p_draft.set_defaults(func=cmd_draft)

    p_fill = sub.add_parser("fill", help="把填好的 draft.md 合并回 analysis.json（hl 留空取 ph）")
    p_fill.add_argument("draft")
    p_fill.add_argument("-j", "--json", required=True, help="skeleton 产出的 analysis.json")
    p_fill.add_argument("-o", "--output", help="输出 JSON，默认就地覆盖 -j")
    p_fill.set_defaults(func=cmd_fill)

    p_ver = sub.add_parser("verify", help="注入结果静态验收：空字段/豆腐块/双重转义/词汇表/source/页高")
    p_ver.add_argument("html")
    p_ver.add_argument("-j", "--json", help="可选：对照 analysis.json 核对词汇表条数")
    p_ver.set_defaults(func=cmd_verify)

    p_chk = sub.add_parser("check", help="只校验分析 JSON，不写文件")
    p_chk.add_argument("html")
    p_chk.add_argument("-j", "--json", required=True)
    p_chk.set_defaults(func=cmd_check)

    p_inj = sub.add_parser("inject", help="把分析 JSON 注入 HTML（默认就地改写，自动备份原件）")
    p_inj.add_argument("html")
    p_inj.add_argument("-j", "--json", required=True)
    p_inj.add_argument("-o", "--output")
    p_inj.set_defaults(func=cmd_inject)

    p_shot = sub.add_parser("shot", help="CDP 全页截图：浅/深 × 精读/原文 四图 + 可读分片")
    p_shot.add_argument("html")
    p_shot.add_argument("-d", "--outdir", help="图片输出目录，默认与 HTML 同目录")
    p_shot.add_argument("-W", "--width", type=int, default=1300)
    p_shot.add_argument("-H", "--height", type=int, default=0,
                        help="手动指定页高，默认按 getLayoutMetrics 自动取全页")
    p_shot.add_argument("-P", "--part", type=int, default=1500,
                        help="精读模式可读分片高度（默认 1500px）")
    p_shot.set_defaults(func=cmd_shot)

    p_open = sub.add_parser("open", help="用系统默认浏览器打开成品 HTML")
    p_open.add_argument("html")
    p_open.set_defaults(func=cmd_open)

    args = ap.parse_args()
    try:
        args.func(args)
    except (ValueError, FileNotFoundError) as e:
        sys.exit(f"错误: {e}")


if __name__ == "__main__":
    main()
