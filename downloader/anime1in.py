from utils import *

class Anime1in:
    _selected_source_idx = None  # 0-based index, stable across episodes in batch
    BASE = 'https://anime1.in'

    def Link_Validate(site):
        Anime1in._selected_source_idx = None  # reset for each new URL
        title, link = Anime1in.Get_Title_Link(site, get_link=False)
        if title is None:
            print('err: None')
            return 0
        if link == 1:
            return 21  # single episode
        if link == 2:
            return 22  # series
        return 0

    def _is_episode(site):
        path = site.rstrip('/').split('/')[-1]
        # episode pages end with a long numeric id, e.g. ...-10013000
        return bool(re.search(r'-\d{4,}$', path))

    def _Get_Sources(soup, referer):
        """Extract .vframe iframes, fetch each player page concurrently, return list of (name, m3u8_url)."""
        iframes = [i for i in soup.select('iframe.vframe') if i.get('src')]
        if not iframes:
            return []

        player_urls = [(f"來源{idx+1}", Anime1in._resolve_url(Anime1in.BASE + '/', i['src']))
                       for idx, i in enumerate(iframes)]

        def fetch_m3u8(name, player_url):
            try:
                r = requests.get(player_url, headers={**global_headers, 'Referer': referer}, timeout=10)
                m = re.search(r'<source[^>]+src="([^"]+\.m3u8)"', r.content.decode('utf-8'))
                return name, m.group(1) if m else None
            except Exception:
                return name, None

        results = [None] * len(player_urls)
        with concurrent.futures.ThreadPoolExecutor(len(player_urls)) as ex:
            futures = {ex.submit(fetch_m3u8, name, url): i for i, (name, url) in enumerate(player_urls)}
            for f in concurrent.futures.as_completed(futures):
                results[futures[f]] = f.result()

        return [(name, url) for name, url in results if url]

    def _resolve_url(base_url, path):
        if path.startswith('http'):
            return path
        if path.startswith('//'):
            return 'https:' + path
        if path.startswith('/'):
            from urllib.parse import urlparse
            p = urlparse(base_url)
            return f"{p.scheme}://{p.netloc}{path}"
        return '/'.join(base_url.split('/')[:-1]) + '/' + path

    def Resolution_Check(sources, TMP):
        """Check resolution for each source concurrently. Tier1: RESOLUTION tag. Tier2: chunk size estimate."""
        preview_path = TMP + '/preview'
        if not os.path.isdir(preview_path):
            os.makedirs(preview_path)

        def check_one(i, name, m3u8_url):
            try:
                r = requests.get(m3u8_url, headers=global_headers, timeout=10)
                content = r.text

                # Tier 1: RESOLUTION tag in master playlist
                res_match = re.search(r'RESOLUTION=(\d+x\d+)', content)
                if res_match:
                    return i, f"({res_match.group(1)})"

                # Tier 2: resolve sub-playlist, download first chunk, estimate
                sub_match = re.search(r'^(?!#)([^\s]+\.m3u8)', content, re.MULTILINE)
                if sub_match:
                    sub_url = Anime1in._resolve_url(m3u8_url, sub_match.group(1))
                    r2 = requests.get(sub_url, headers=global_headers, timeout=10)
                    content = r2.text
                    sub_url_final = sub_url
                else:
                    sub_url_final = m3u8_url

                chunk_lines = [l.strip() for l in content.split('\n')
                               if l.strip() and not l.startswith('#')]
                if not chunk_lines:
                    return i, '(Invalid)'

                first_chunk = Anime1in._resolve_url(sub_url_final, chunk_lines[0])
                download_chunk(first_chunk, i, preview_path, timeout=10, retry=1)
                ts_path = f"{preview_path}/{i}.ts"
                if not os.path.isfile(ts_path) or os.path.getsize(ts_path) == 0:
                    return i, '(Invalid)'

                quality = Get_Video_Resolution(ts_path, len(chunk_lines))
                return i, f"({quality})"
            except Exception as e:
                if DEBUG: print(f"Debug: Resolution check failed for source {i}: {e}")
                return i, '(Invalid)'

        results = ['(Invalid)'] * len(sources)
        with concurrent.futures.ThreadPoolExecutor(len(sources)) as ex:
            futures = [ex.submit(check_one, i, n, u) for i, (n, u) in enumerate(sources)]
            for f in concurrent.futures.as_completed(futures):
                i, label = f.result()
                results[i] = label
        return results

    def _Prompt_Source(sources, TMP):
        """Show source list with optional resolution check, return selected index."""
        res_check = input("檢查畫質(1:是 2:否): ").strip()
        if res_check == '1':
            print("檢查畫質...")
            resolutions = Anime1in.Resolution_Check(sources, TMP)
            show = '\n'
            for i, (name, _) in enumerate(sources):
                show += f"{i+1}.{name} {resolutions[i]}\n"
            print(show)
        else:
            print('\n'.join([f"{i+1}.{n}" for i, (n, _) in enumerate(sources)]))
        sel = input(f"選擇分流(1~{len(sources)}): ").strip()
        if not sel:
            print("未選擇分流")
            return None
        return int(sel) - 1

    def _Fetch_Chunklist(m3u8_url, TMP):
        """Fetch master m3u8, resolve sub-playlist if needed, return chunklist."""
        tmpPath = TMP + '/gimy'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        r = requests.get(m3u8_url, headers=global_headers, timeout=15)
        content = r.text
        sub_match = re.search(r'^(?!#)([^\s]+\.m3u8)', content, re.MULTILINE)
        if sub_match:
            sub_url = Anime1in._resolve_url(m3u8_url, sub_match.group(1))
            r2 = requests.get(sub_url, headers=global_headers, timeout=15)
            content = r2.text
            m3u8_url = sub_url
        return Parse_m3u8(TMP, content, m3u8_url)

    def Get_Title_Link(site, get_link=True):
        try:
            r = requests.get(site, headers=global_headers, timeout=10)
            soup = bs(r.content.decode('utf-8'), 'html.parser')
            title_tag = soup.find('title')
            if not title_tag:
                return None, None
            raw_title = title_tag.get_text()
            title = raw_title.split(' – Anime1.in')[0].strip()

            if Anime1in._is_episode(site):
                if not get_link:
                    return FileNameClean(title), 1
                TMP = (os.getcwd() + '/Tmp').replace('\\', '/')
                sources = Anime1in._Get_Sources(soup, site)
                if not sources:
                    print("Err: no sources found")
                    return None, None

                if len(sources) == 1:
                    idx = 0
                else:
                    if Anime1in._selected_source_idx is None:
                        idx = Anime1in._Prompt_Source(sources, TMP)
                        if idx is None:
                            return None, None
                        Anime1in._selected_source_idx = idx
                    idx = Anime1in._selected_source_idx

                if idx >= len(sources):
                    print(f"Warning: source {idx+1} not available, using first")
                    idx = 0
                _, m3u8_url = sources[idx]

                chunklist = Anime1in._Fetch_Chunklist(m3u8_url, TMP)
                return FileNameClean(title), chunklist

            else:
                # Series page — paginate, collect all episode links.
                # Page 1 needs a trailing slash (404 without); later pages use /page/N (no trailing slash).
                base = site.rstrip('/')
                all_links = []
                page = 1
                while True:
                    page_url = f"{base}/" if page == 1 else f"{base}/page/{page}"
                    rp = requests.get(page_url, headers=global_headers, timeout=10)
                    sp = bs(rp.content.decode('utf-8'), 'html.parser')
                    h2s = sp.find_all('h2')
                    ep_links = [h.find('a')['href'] for h in h2s if h.find('a')]
                    if not ep_links:
                        break
                    all_links.extend(ep_links)
                    page += 1
                all_links.reverse()  # site shows descending, reverse for ascending
                links = [Anime1in._resolve_url(Anime1in.BASE + '/', href) for href in all_links]
                if not get_link:
                    return FileNameClean(title), 2
                return FileNameClean(title), links

        except Exception as e:
            print("Err: Get_Title_Link", e)
            return None, None

    def Download_Request(site, TMP, downloadPath):
        tmpPath = TMP + '/gimy'
        tmpfile = tmpPath + '/0.m3u8'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        title, chunks = Anime1in.Get_Title_Link(site)
        if not chunks or not title:
            print("Connection Failed. Source may be invalid!")
            return False
        print(title)

        if Download_Chunks(chunks, TMP):
            return False

        if MP4convert(tmpfile, downloadPath + '/' + title + '.mp4'):
            return False

        shutil.rmtree(tmpPath)
        return True
