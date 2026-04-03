from utils import *

class MovieFFM:
    _selected_source_idx = None

    def Link_Validate(site):
        MovieFFM._selected_source_idx = None
        title, sentinel = MovieFFM.Get_Title_Link(site, False)
        if title is None:
            return 0
        return 18

    def _extract_json_array(text, key):
        """Find 'key: [...]' in text and return the JSON array string via bracket counting."""
        m = re.search(rf'{key}:\s*\[', text)
        if not m:
            return None
        start = m.end() - 1  # points to opening '['
        depth = 0
        for i, c in enumerate(text[start:]):
            if c == '[':
                depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    return text[start:start + i + 1]
        return None

    def _Parse_Vue_Data(html):
        """Extract videourls and tables from inline Vue script. Returns (videourls, tables) or (None, None).
        Supports both old format (nested videourls + tables) and new flat format (flat list with source/ep keys)."""
        m = re.search(r"new Vue\(\{[\s\S]*?el:\s*['\"]#(?:dooplay_player|playcontainer)['\"][\s\S]*?\}\)", html)
        if not m:
            return None, None
        script = m.group(0)

        vu_raw = MovieFFM._extract_json_array(script, 'videourls')
        if not vu_raw:
            return None, None

        try:
            vu_parsed = json.loads(vu_raw)
        except json.JSONDecodeError:
            return None, None

        # New flat format: [{source: int, url: str, type: str, ep: int}, ...]
        if vu_parsed and isinstance(vu_parsed[0], dict) and 'source' in vu_parsed[0]:
            # Group by source index
            by_source = {}
            for item in vu_parsed:
                s = item['source']
                if s not in by_source:
                    by_source[s] = []
                by_source[s].append(item)
            # Sort each source's episodes by ep number
            videourls = []
            tables = []
            for s in sorted(by_source.keys()):
                eps = sorted(by_source[s], key=lambda x: x.get('ep', 0))
                videourls.append(eps)
                tables.append({'ht': f'Source {s+1}'})
            return videourls, tables

        # Old nested format: videourls is list of lists, tables is separate
        tb_raw = MovieFFM._extract_json_array(script, 'tables')
        if not tb_raw:
            return None, None
        try:
            return vu_parsed, json.loads(tb_raw)
        except json.JSONDecodeError:
            return None, None

    def _resolve_sub_m3u8(master_url):
        """Fetch m3u8, resolve master→sub if needed. Returns (content, final_url)."""
        r = requests.get(master_url, headers=global_headers, timeout=15)
        content = r.text
        sub_match = re.search(r'^(?!#)([^\s]+\.m3u8)', content, re.MULTILINE)
        if sub_match:
            sub_path = sub_match.group(1)
            if sub_path.startswith('http'):
                sub_url = sub_path
            elif sub_path.startswith('/'):
                from urllib.parse import urlparse
                p = urlparse(master_url)
                sub_url = f"{p.scheme}://{p.netloc}{sub_path}"
            else:
                sub_url = '/'.join(master_url.split('/')[:-1]) + '/' + sub_path
            r2 = requests.get(sub_url, headers=global_headers, timeout=15)
            return r2.text, sub_url
        return content, master_url

    def Resolution_Check(sources, TMP):
        """Check resolution of first episode for each source concurrently.
        sources: list of (name, ep_count, [m3u8_url, ...])
        Returns list of resolution label strings."""
        preview_path = TMP + '/preview'
        if not os.path.isdir(preview_path):
            os.makedirs(preview_path)

        def check_one(i, m3u8_url):
            try:
                r = requests.get(m3u8_url, headers=global_headers, timeout=10)
                content = r.text

                res_match = re.search(r'RESOLUTION=(\d+x\d+)', content)
                if res_match:
                    return i, f"({res_match.group(1)})"

                sub_content, sub_url = MovieFFM._resolve_sub_m3u8(m3u8_url)
                chunk_lines = [l.strip() for l in sub_content.split('\n')
                               if l.strip() and not l.startswith('#')]
                total_chunks = len(chunk_lines)
                if not chunk_lines:
                    return i, '(Invalid)'

                first_chunk = chunk_lines[0]
                if not first_chunk.startswith('http'):
                    base = '/'.join(sub_url.split('/')[:-1])
                    first_chunk = base + '/' + first_chunk

                download_chunk(first_chunk, i, preview_path, timeout=10, retry=1)
                ts_path = f"{preview_path}/{i}.ts"
                if not os.path.isfile(ts_path) or os.path.getsize(ts_path) == 0:
                    return i, '(Invalid)'

                quality = Get_Video_Resolution(ts_path, total_chunks)
                return i, f"({quality})"
            except Exception as e:
                if DEBUG: print(f"Debug: Resolution check failed for source {i}: {e}")
                return i, '(Invalid)'

        # Use first episode URL from each source
        first_urls = [(i, s[2][0]) for i, s in enumerate(sources) if s[2]]
        results = ['(Invalid)'] * len(sources)
        with concurrent.futures.ThreadPoolExecutor(len(first_urls)) as ex:
            futures = [ex.submit(check_one, i, url) for i, url in first_urls]
            for f in concurrent.futures.as_completed(futures):
                i, label = f.result()
                results[i] = label
        return results

    def Get_Title_Link(site, get_link=True):
        r = requests.get(site, headers=global_headers, timeout=15)
        html = r.content.decode('utf-8')
        soup = bs(html, 'html.parser')

        title_tag = soup.find('title')
        if not title_tag:
            return None, None
        raw_title = title_tag.get_text()
        title = re.sub(r'\s*[-|]\s*MovieFFM.*', '', raw_title, flags=re.IGNORECASE).strip()
        title = FileNameClean(title)
        if not title:
            return None, None

        if not get_link:
            return title, 2

        TMP = (os.getcwd() + "/Tmp").replace('\\', '/')
        videourls, tables = MovieFFM._Parse_Vue_Data(html)
        if videourls is None:
            print("No video sources found")
            return None, None

        # Build source list: (name, ep_count, [m3u8_url, ...])
        sources = []
        for i, tbl in enumerate(tables):
            if i >= len(videourls):
                break
            name = re.sub(r'<[^>]+>', '', tbl.get('ht', f'Source {i+1}')).strip()
            eps = videourls[i]
            sources.append((name, len(eps), [e['url'] for e in eps]))

        if not sources:
            print("No sources found")
            return None, None

        if MovieFFM._selected_source_idx is None:
            res_check = input("檢查畫質(1:是 2:否): ").strip()
            if res_check == '1':
                print("檢查畫質...")
                resolutions = MovieFFM.Resolution_Check(sources, TMP)
                showStr = '\n'
                for i, s in enumerate(sources):
                    showStr += f"{i+1}.{s[0]} ({s[1]}集) {resolutions[i]}\n"
                print(showStr)
            else:
                print('\n'.join([f"{i+1}.{s[0]} ({s[1]}集)" for i, s in enumerate(sources)]))
            sel = input(f"選擇來源(1~{len(sources)}): ").strip()
            if not sel:
                print("未選擇來源")
                return None, None
            MovieFFM._selected_source_idx = int(sel) - 1

        idx = MovieFFM._selected_source_idx
        m3u8_urls = sources[idx][2]
        return title, m3u8_urls

    def _Fetch_Chunklist(m3u8_url, TMP):
        """Fetch m3u8 URL, resolve master playlist if needed, return chunklist."""
        tmpPath = TMP + '/gimy'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        content, final_url = MovieFFM._resolve_sub_m3u8(m3u8_url)
        return Parse_m3u8(TMP, content, final_url)

    def Download_Request(m3u8_url, episode_title, TMP, downloadPath):
        tmpPath = TMP + '/gimy'
        tmpfile = tmpPath + '/0.m3u8'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        chunks = MovieFFM._Fetch_Chunklist(m3u8_url, TMP)
        if not chunks:
            print(f"Connection Failed: {episode_title}")
            return False
        print(episode_title)

        if Download_Chunks(chunks, TMP):
            return False

        if MP4convert(tmpfile, downloadPath + '/' + episode_title + '.mp4'):
            return False

        shutil.rmtree(tmpPath)
        return True
