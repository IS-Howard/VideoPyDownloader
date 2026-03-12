from utils import *

class Mmov:
    _selected_source_idx = None  # None = single-ep mode (prompt), int = batch mode (skip prompt)

    def Link_Validate(site):
        Mmov._selected_source_idx = None
        if '/vodplay/' in site:
            return 11  # single episode
        if '/vod/' in site:
            return 12  # series detail
        return 0

    def _Extract_Sources(soup):
        """Parse series page → list of (source_name, [episode_urls]).
        Structure: div.stui-pannel > div.stui-pannel__head > h3.title
                                   > ul.stui-content__playlist > li > a
        """
        sources = []
        for panel in soup.select('div.stui-pannel'):
            h3 = panel.select_one('h3.title')
            ul = panel.select_one('ul.stui-content__playlist')
            if not h3 or not ul:
                continue
            name = h3.get_text(strip=True)
            links = []
            for a in ul.find_all('a', href=True):
                href = a['href']
                if not href.startswith('http'):
                    href = 'https://tw.mmov.app' + href
                links.append(href)
            if links:
                sources.append((name, links))
        return sources

    def _Get_Sources_For_Episode(show_id, ep_num):
        """Fetch series page, return [(source_name, episode_url)] for the given ep_num."""
        series_url = f'https://tw.mmov.app/vod/{show_id}.html'
        r = requests.get(series_url, headers=global_headers, timeout=15)
        soup = bs(r.content.decode('utf-8'), 'html.parser')
        all_sources = Mmov._Extract_Sources(soup)
        result = []
        for name, urls in all_sources:
            ep_url = next((u for u in urls if re.search(rf'-{ep_num}\.html$', u)), None)
            if ep_url:
                result.append((name, ep_url))
        return result

    def _Get_VideoSrc(html):
        """Extract var videoSrc = '...' m3u8 URL from episode page HTML."""
        m = re.search(r"var videoSrc\s*=\s*'([^']+)'", html)
        return m.group(1) if m else None

    def _Get_VideoSrc_From_Url(ep_url):
        """Fetch episode page and return videoSrc m3u8 URL."""
        r = requests.get(ep_url, headers=global_headers, timeout=15)
        return Mmov._Get_VideoSrc(r.content.decode('utf-8'))

    def _Resolve_Sub_M3u8(m3u8_url, content=None):
        """Fetch m3u8, return (content, final_url) — resolves master→sub if needed."""
        if content is None:
            r = requests.get(m3u8_url, headers=global_headers, timeout=15)
            content = r.text
        sub_match = re.search(r'^(?!#)([^\s]+\.m3u8)', content, re.MULTILINE)
        if sub_match:
            sub_path = sub_match.group(1)
            if sub_path.startswith('http'):
                sub_url = sub_path
            elif sub_path.startswith('/'):
                from urllib.parse import urlparse
                p = urlparse(m3u8_url)
                sub_url = f"{p.scheme}://{p.netloc}{sub_path}"
            else:
                sub_url = '/'.join(m3u8_url.split('/')[:-1]) + '/' + sub_path
            r2 = requests.get(sub_url, headers=global_headers, timeout=30)
            return r2.text, sub_url
        return content, m3u8_url

    def _Fetch_Chunklist(m3u8_url, TMP):
        """Fetch m3u8, resolve master playlist if needed, return chunklist."""
        tmpPath = TMP + '/gimy'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        content, final_url = Mmov._Resolve_Sub_M3u8(m3u8_url)
        return Parse_m3u8(TMP, content, final_url)

    def Resolution_Check(sources_with_urls, TMP):
        """Parallel resolution check. sources_with_urls = [(name, ep_url), ...]"""
        preview_path = TMP + '/preview'
        if not os.path.isdir(preview_path):
            os.makedirs(preview_path)

        def check_one(i, name, ep_url):
            try:
                m3u8_url = Mmov._Get_VideoSrc_From_Url(ep_url)
                if not m3u8_url:
                    return i, '(Invalid)'
                r = requests.get(m3u8_url, headers=global_headers, timeout=10)
                content = r.text
                # Try exact RESOLUTION from master playlist
                res_match = re.search(r'RESOLUTION=(\d+x\d+)', content)
                if res_match:
                    return i, f"({res_match.group(1)})"
                # Estimate from first chunk size × total chunks
                sub_content, sub_url = Mmov._Resolve_Sub_M3u8(m3u8_url, content)
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
            except Exception:
                return i, '(Invalid)'

        results = ['(Invalid)'] * len(sources_with_urls)
        with concurrent.futures.ThreadPoolExecutor(len(sources_with_urls)) as ex:
            futures = [ex.submit(check_one, i, n, u) for i, (n, u) in enumerate(sources_with_urls)]
            for f in concurrent.futures.as_completed(futures):
                i, label = f.result()
                results[i] = label
        return results

    def _Prompt_Source(sources_with_urls, TMP):
        """Show source list with optional resolution check, return selected (name, ep_url)."""
        res_check = input("檢查畫質(1:是 2:否): ").strip()
        if res_check == '1':
            print("檢查畫質...")
            resolutions = Mmov.Resolution_Check(sources_with_urls, TMP)
            showStr = '\n'
            for i, (name, _) in enumerate(sources_with_urls):
                showStr += f"{i+1}.{name} {resolutions[i]}\n"
            print(showStr)
        else:
            print('\n'.join([f"{i+1}.{s[0]}" for i, s in enumerate(sources_with_urls)]))
        sel = input(f"選擇來源(1~{len(sources_with_urls)}): ").strip()
        if not sel:
            print("未選擇來源")
            return None
        return sources_with_urls[int(sel) - 1]

    def _Prompt_Source_Series(sources, TMP):
        """For series: show source groups with optional resolution check, return selected index."""
        res_check = input("檢查畫質(1:是 2:否): ").strip()
        if res_check == '1':
            print("檢查畫質...")
            # Use first episode of each source group for resolution sampling
            ep1_pairs = [(name, urls[0]) for name, urls in sources if urls]
            resolutions = Mmov.Resolution_Check(ep1_pairs, TMP)
            showStr = '\n'
            for i, (name, _) in enumerate(sources):
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
        html = r.content.decode('utf-8')
        soup = bs(html, 'html.parser')

        if '/vodplay/' not in site:
            # Series detail page: /vod/{id}.html
            h1 = soup.find('h1')
            title = h1.get_text(strip=True) if h1 else ''
            if not title:
                title_tag = soup.find('title')
                if title_tag:
                    title = re.sub(r'免費線上看.*', '', title_tag.get_text()).strip()
            if not title:
                return None, None

            if get_link:
                sources = Mmov._Extract_Sources(soup)
                if not sources:
                    print("No sources found")
                    return None, None
                idx = Mmov._Prompt_Source_Series(sources, TMP)
                if idx is None:
                    return None, None
                Mmov._selected_source_idx = idx
                return FileNameClean(title), sources[idx][1]
            else:
                return FileNameClean(title), 2

        else:
            # Episode player page: /vodplay/{id}/{src}-{ep}.html
            title_tag = soup.find('title')
            raw = title_tag.get_text() if title_tag else ''
            # e.g. "喜人奇妙夜第01期上-綜藝免費線上看-MMOV線上看" → "喜人奇妙夜第01期上"
            title = raw.split('-')[0].strip() if '-' in raw else raw.strip()
            if not title:
                return None, None

            if get_link:
                if Mmov._selected_source_idx is None:
                    # Single episode mode: show all sources with optional resolution check
                    m = re.search(r'/vodplay/(\d+)/\d+-(\d+)\.html', site)
                    if not m:
                        return None, None
                    show_id, ep_num = m.group(1), m.group(2)
                    sources_with_urls = Mmov._Get_Sources_For_Episode(show_id, ep_num)
                    if not sources_with_urls:
                        print("No sources found")
                        return None, None
                    picked = Mmov._Prompt_Source(sources_with_urls, TMP)
                    if not picked:
                        return None, None
                    _, ep_url = picked
                    m3u8_url = Mmov._Get_VideoSrc_From_Url(ep_url)
                else:
                    # Batch mode: URL already points to chosen source, extract directly
                    m3u8_url = Mmov._Get_VideoSrc(html)

                if not m3u8_url:
                    print("videoSrc not found")
                    return None, None
                chunklist = Mmov._Fetch_Chunklist(m3u8_url, TMP)
                return FileNameClean(title), chunklist
            else:
                return FileNameClean(title), 1

    def Download_Request(site, TMP, downloadPath):
        tmpPath = TMP + '/gimy'
        tmpfile = tmpPath + '/0.m3u8'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        title, chunks = Mmov.Get_Title_Link(site)
        if not chunks or not title:
            print("Connection Failed. Source may be invalid!")
            return False
        print(title)

        Download_Chunks(chunks, TMP)

        if MP4convert(tmpfile, downloadPath + '/' + title + '.mp4'):
            return False

        shutil.rmtree(tmpPath)
        return True
