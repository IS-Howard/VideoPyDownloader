from utils import *
from urllib.parse import urlparse, unquote
import base64
import json

class Yanetflix:
    _selected_sid = None  # source sid for batch mode

    # Sources with these 'from' values return encrypted tokens, not direct m3u8
    _UNUSABLE_SOURCES = {'NBY', 'KMQP', 'kemi', 'Netflix'}

    def Link_Validate(site):
        Yanetflix._selected_sid = None
        title, link = Yanetflix.Get_Title_Link(site, False)
        if title is None or link is None:
            return 0
        if link == 1:
            return 19  # single episode
        if link == 2:
            return 20  # series
        return 0

    def _decode_player_url(encoded):
        """Decode player_aaaa url field: base64 → url-decode (encrypt:2)."""
        try:
            step1 = base64.b64decode(encoded).decode('utf-8')
            step2 = unquote(step1)
            if step2.startswith('http'):
                return step2
            return None
        except Exception:
            return None

    def _resolve_url(base_url, path):
        if path.startswith('http'):
            return path
        if path.startswith('/'):
            p = urlparse(base_url)
            return f"{p.scheme}://{p.netloc}{path}"
        return '/'.join(base_url.split('/')[:-1]) + '/' + path

    def _Get_M3u8_Url(episode_url):
        """Extract m3u8 URL from play page via player_aaaa variable."""
        r = requests.get(episode_url, headers=global_headers, timeout=15)
        text = r.content.decode('utf-8')
        m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', text, re.DOTALL)
        if not m:
            return None, None
        data = json.loads(m.group(1).replace('\\/', '/'))
        from_val = data.get('from', '')
        url_encoded = data.get('url', '')
        return from_val, Yanetflix._decode_player_url(url_encoded)

    def _Fetch_Chunklist(m3u8_url, TMP):
        """Fetch m3u8, resolve master playlist if needed, return chunklist."""
        tmpPath = TMP + '/gimy'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        r = requests.get(m3u8_url, headers=global_headers, timeout=30)
        content = r.text
        sub_match = re.search(r'^(?!#)([^\s]+\.m3u8)', content, re.MULTILINE)
        if sub_match:
            sub_url = Yanetflix._resolve_url(m3u8_url, sub_match.group(1))
            r2 = requests.get(sub_url, headers=global_headers, timeout=30)
            content = r2.text
            m3u8_url = sub_url
        # Chunks may have query strings (e.g. .ts?hash=...) which Parse_m3u8
        # doesn't recognize. Strip query strings from chunk lines for Parse_m3u8,
        # but keep full URLs for download.
        cleaned_lines = []
        raw_lines = content.split('\n')
        for line in raw_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and '.ts' in stripped:
                # Remove query string for m3u8 file, keep original for chunklist
                cleaned_lines.append(re.sub(r'\?.*$', '', stripped))
            else:
                cleaned_lines.append(line)
        cleaned_content = '\n'.join(cleaned_lines)
        Parse_m3u8(TMP, cleaned_content, m3u8_url)
        # Build chunklist from original content with full URLs (including query strings)
        chunklist = []
        base = '/'.join(m3u8_url.split('/')[:-1])
        for line in raw_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and '.ts' in stripped:
                if stripped.startswith('http'):
                    chunklist.append(stripped)
                else:
                    chunklist.append(base + '/' + stripped)
        return chunklist

    def _Resolve_Sub_M3u8(master_url):
        """Fetch m3u8, return (content, final_url) — resolves master→sub if needed."""
        r = requests.get(master_url, headers=global_headers, timeout=15)
        content = r.text
        sub_match = re.search(r'^(?!#)([^\s]+\.m3u8)', content, re.MULTILINE)
        if sub_match:
            sub_url = Yanetflix._resolve_url(master_url, sub_match.group(1))
            r2 = requests.get(sub_url, headers=global_headers, timeout=15)
            return r2.text, sub_url
        return content, master_url

    def Resolution_Check(sources, TMP):
        """Parallel resolution check for all sources.
        sources: list of (name, sid, first_ep_url)
        """
        preview_path = TMP + '/preview'
        if not os.path.isdir(preview_path):
            os.makedirs(preview_path)

        def check_one(i, name, sid, ep_url):
            try:
                from_val, m3u8_url = Yanetflix._Get_M3u8_Url(ep_url)
                if not m3u8_url or from_val in Yanetflix._UNUSABLE_SOURCES:
                    return i, '(Invalid)'
                r = requests.get(m3u8_url, headers=global_headers, timeout=10)
                content = r.text
                # Tier 1: exact resolution from master playlist RESOLUTION tag
                res_match = re.search(r'RESOLUTION=(\d+x\d+)', content)
                if res_match:
                    return i, f"({res_match.group(1)})"
                # Tier 2: resolve sub-playlist, download first chunk for size estimate
                sub_content, sub_url = Yanetflix._Resolve_Sub_M3u8(m3u8_url)
                chunk_lines = [l.strip() for l in sub_content.split('\n')
                               if l.strip() and not l.startswith('#')]
                if not chunk_lines:
                    return i, '(Invalid)'
                total_chunks = len(chunk_lines)
                first_chunk = Yanetflix._resolve_url(sub_url, chunk_lines[0])
                download_chunk(first_chunk, i, preview_path, timeout=10, retry=1)
                ts_path = f"{preview_path}/{i}.ts"
                if not os.path.isfile(ts_path) or os.path.getsize(ts_path) == 0:
                    return i, '(Invalid)'
                quality = Get_Video_Resolution(ts_path, total_chunks)
                return i, f"({quality})"
            except Exception as e:
                if DEBUG: print(f"Debug: Resolution check failed for source {i}: {e}")
                return i, '(Invalid)'

        results = ['(Invalid)'] * len(sources)
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(sources)) as ex:
            futures = [ex.submit(check_one, i, n, s, u) for i, (n, s, u) in enumerate(sources)]
            for f in concurrent.futures.as_completed(futures):
                i, label = f.result()
                results[i] = label
        return results

    def _Prompt_Source(sources, TMP):
        """Prompt user to select source with optional resolution check. Returns sid."""
        res_check = input("檢查畫質(1:是 2:否): ").strip()
        if res_check == '1':
            print("檢查畫質...")
            resolutions = Yanetflix.Resolution_Check(sources, TMP)
            showStr = '\n'
            for i, (name, _, _) in enumerate(sources):
                showStr += f"{i+1}.{name} {resolutions[i]}\n"
            print(showStr)
        else:
            print('\n'.join([f"{i+1}.{s[0]}" for i, s in enumerate(sources)]))
        sel = input(f"選擇來源(1~{len(sources)}): ").strip()
        if not sel:
            print("未選擇來源")
            return None
        return int(sel) - 1

    def Get_Title_Link(site, get_link=True):
        TMP = (os.getcwd() + "/Tmp").replace('\\', '/')
        r = requests.get(site, headers=global_headers, timeout=15)
        text = r.content.decode('utf-8')
        soup = bs(text, 'html.parser')
        prefix = 'https://yanetflix.com'

        title_tag = soup.find('title')
        if not title_tag:
            return None, None
        raw_title = title_tag.get_text()

        if '/detail/' in site:
            # Series/detail page: /detail/{id}.html
            # Title: "{name}_{type} - 奈飞工厂-..."
            title = re.sub(r'[_\s]*[-–]?\s*奈飞工厂.*', '', raw_title)
            title = re.sub(r'_[^\s]*$', '', title).strip()
            if not get_link:
                return FileNameClean(title), 2

            # Parse tabs: .anthology-tab a.swiper-slide
            tabs = soup.select('.anthology-tab .swiper-slide')
            # Parse episode lists: .anthology-list-box ul
            ep_boxes = soup.select('.anthology-list-box')

            if not tabs or not ep_boxes or len(tabs) != len(ep_boxes):
                print("No sources found")
                return None, None

            # Build raw sources list: (tab_name, sid, first_ep_url)
            raw_sources = []
            for i, (tab, box) in enumerate(zip(tabs, ep_boxes)):
                # Tab text includes badge count appended (e.g. "蓝光-316"), strip it
                badge = tab.select_one('.badge')
                if badge:
                    badge.decompose()
                tab_name = tab.get_text(strip=True)
                first_a = box.select_one('li a')
                if not first_a:
                    continue
                href = first_a.get('href', '')
                sid_m = re.search(r'/play/\d+-(\d+)-', href)
                if not sid_m:
                    continue
                sid = int(sid_m.group(1))
                ep_url = prefix + href
                raw_sources.append((tab_name, sid, ep_url))

            # Concurrent pre-check: filter out sources with encrypted/unusable URLs
            def _check_source(item):
                name, sid, ep_url = item
                try:
                    from_val, m3u8_url = Yanetflix._Get_M3u8_Url(ep_url)
                    if from_val in Yanetflix._UNUSABLE_SOURCES or not m3u8_url:
                        return None
                    return item
                except Exception:
                    return None

            print("篩選可用來源...")
            sources = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(raw_sources)) as ex:
                results = list(ex.map(_check_source, raw_sources))
            sources = [r for r in results if r is not None]

            if not sources:
                print("No usable sources found")
                return None, None

            if len(sources) == 1:
                sel_idx = 0
            else:
                sel_idx = Yanetflix._Prompt_Source(sources, TMP)
            if sel_idx is None:
                return None, None

            sel_sid = sources[sel_idx][1]
            Yanetflix._selected_sid = sel_sid

            # Find the corresponding episode box for the selected sid
            # Re-scan all boxes to find the one with matching sid
            for box in ep_boxes:
                first_a = box.select_one('li a')
                if not first_a:
                    continue
                href = first_a.get('href', '')
                sid_m = re.search(r'/play/\d+-(\d+)-', href)
                if sid_m and int(sid_m.group(1)) == sel_sid:
                    links = [prefix + a['href'] for a in box.select('li a')]
                    return FileNameClean(title), links

            return None, None

        elif '/play/' in site:
            # Single play page: /play/{id}-{sid}-{ep}.html
            # Title: "奈飞工厂热门{type}-《{name}》{ep_num} - ..."
            m = re.search(r'《(.+?)》', raw_title)
            if m:
                title = m.group(1)
            else:
                title = re.sub(r'[_\s]*[-–]?\s*奈飞工厂.*', '', raw_title).strip()

            if not get_link:
                return FileNameClean(title), 1

            from_val, m3u8_url = Yanetflix._Get_M3u8_Url(site)
            if not m3u8_url or from_val in Yanetflix._UNUSABLE_SOURCES:
                # Try to find a usable source by checking other sids
                id_m = re.search(r'/play/(\d+)-(\d+)-(\d+)', site)
                if id_m:
                    vid_id, _, ep = id_m.group(1), id_m.group(2), id_m.group(3)
                    if Yanetflix._selected_sid:
                        alt_url = f"{prefix}/play/{vid_id}-{Yanetflix._selected_sid}-{ep}.html"
                        from_val, m3u8_url = Yanetflix._Get_M3u8_Url(alt_url)
                if not m3u8_url or from_val in Yanetflix._UNUSABLE_SOURCES:
                    print("No usable m3u8 source found")
                    return None, None

            return FileNameClean(title), Yanetflix._Fetch_Chunklist(m3u8_url, TMP)

        return None, None

    def Download_Request(site, TMP, downloadPath, max_threads=15):
        tmpPath = TMP + '/gimy'
        tmpfile = tmpPath + '/0.m3u8'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        title, chunks = Yanetflix.Get_Title_Link(site)
        if not chunks or not title:
            print("Connection Failed. Source may be invalid!")
            if DEBUG: print(f"Debug: title='{title}', chunks='{chunks}'\n")
            return False
        print(title)

        if Download_Chunks(chunks, TMP):
            return False

        if MP4convert(tmpfile, downloadPath + '/' + title + ".mp4"):
            return False

        shutil.rmtree(tmpPath)
        return True
