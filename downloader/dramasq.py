from utils import *
import json

class Dramasq:
    _selected_source_name = None  # src_site string, stable across episodes

    def Link_Validate(site):
        Dramasq._selected_source_name = None  # reset for each new URL
        title, link = Dramasq.Get_Title_Link(site, False)
        if title is None or link is None:
            return 0
        if link == 1:
            return 15  # single episode
        if link == 2:
            return 16  # series
        return 0

    def _Get_Sources(vid_id, ep_num):
        """Fetch source list from /drq/ API. Returns list of (src_site, m3u8_url)."""
        url = f"https://dramasq.io/drq/{vid_id}/ep{ep_num}"
        r = requests.get(url, headers=global_headers, timeout=15)
        data = json.loads(r.text)
        return [(p['src_site'], p['play_data']) for p in data.get('video_plays', [])]

    def _resolve_url(base_url, path):
        """Resolve a relative/absolute/full path against a base URL."""
        if path.startswith('http'):
            return path
        if path.startswith('/'):
            from urllib.parse import urlparse
            p = urlparse(base_url)
            return f"{p.scheme}://{p.netloc}{path}"
        return '/'.join(base_url.split('/')[:-1]) + '/' + path

    def _Resolve_Sub_M3u8(master_url):
        """Fetch m3u8, return (content, final_url) — resolves master→sub if needed."""
        r = requests.get(master_url, headers=global_headers, timeout=15)
        content = r.text
        sub_match = re.search(r'^(?!#)([^\s]+\.m3u8)', content, re.MULTILINE)
        if sub_match:
            sub_url = Dramasq._resolve_url(master_url, sub_match.group(1))
            r2 = requests.get(sub_url, headers=global_headers, timeout=15)
            return r2.text, sub_url
        return content, master_url

    def Resolution_Check(sources, TMP):
        """For each source: try exact RESOLUTION from master m3u8, else estimate from chunk+total_chunks.
        All sources are checked concurrently."""
        preview_path = TMP + '/preview'
        if not os.path.isdir(preview_path):
            os.makedirs(preview_path)

        def check_one(i, src_site, m3u8_url):
            try:
                r = requests.get(m3u8_url, headers=global_headers, timeout=10)
                content = r.text

                # 1. Try exact resolution from master playlist RESOLUTION tag
                res_match = re.search(r'RESOLUTION=(\d+x\d+)', content)
                if res_match:
                    return i, f"({res_match.group(1)})"

                # 2. Resolve to sub-playlist, count chunks, download first chunk
                sub_content, sub_url = Dramasq._Resolve_Sub_M3u8(m3u8_url)
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

        results = ['(Invalid)'] * len(sources)
        with concurrent.futures.ThreadPoolExecutor(len(sources)) as ex:
            futures = [ex.submit(check_one, i, s, u) for i, (s, u) in enumerate(sources)]
            for f in concurrent.futures.as_completed(futures):
                i, label = f.result()
                results[i] = label
        return results

    def _Prompt_Source(sources, TMP):
        """Show source list, optionally with resolution check, return selected index."""
        res_check = input("檢查畫質(1:是 2:否): ").strip()
        if res_check == '1':
            print("檢查畫質...")
            resolutions = Dramasq.Resolution_Check(sources, TMP)
            showStr = '\n'
            for i, (src, _) in enumerate(sources):
                showStr += f"{i+1}.{src} {resolutions[i]}\n"
            print(showStr)
        else:
            print('\n'.join([f"{i+1}.{s[0]}" for i, s in enumerate(sources)]))
        sel = input(f"選擇來源(1~{len(sources)}): ").strip()
        if not sel:
            print("未選擇來源")
            return None
        idx = int(sel) - 1
        return sources[idx][0]  # return src_site name, not index

    def _Fetch_Chunklist(m3u8_url, TMP):
        """Fetch m3u8 URL, handle master playlist, return chunklist."""
        tmpPath = TMP + '/gimy'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        r = requests.get(m3u8_url, headers=global_headers, timeout=30)
        content = r.text
        # Handle master playlist
        sub_match = re.search(r'^(?!#)([^\s]+\.m3u8)', content, re.MULTILINE)
        if sub_match:
            sub_url = Dramasq._resolve_url(m3u8_url, sub_match.group(1))
            r2 = requests.get(sub_url, headers=global_headers, timeout=30)
            content = r2.text
            m3u8_url = sub_url
        return Parse_m3u8(TMP, content, m3u8_url)

    def Get_Title_Link(site, get_link=True):
        TMP = (os.getcwd() + "/Tmp").replace('\\', '/')
        r = requests.get(site, headers=global_headers)
        soup = bs(r.content.decode('utf-8'), 'html.parser')

        title_tag = soup.find('title')
        if not title_tag:
            return None, None
        raw_title = title_tag.get_text()

        if 'detail' in site:
            # Series page: /detail/{id}.html
            # Title format: "{name} - DramasQ線上看"
            title = re.sub(r'\s*-\s*DramasQ.*', '', raw_title).strip()

            if get_link:
                ep_links = soup.select('a[href*="/vodplay/"]')
                links = []
                for a in ep_links:
                    href = a['href']
                    if href.startswith('/'):
                        href = 'https://dramasq.io' + href
                    links.append(href)
                links.reverse()  # page shows descending, reverse to ascending

                if not links:
                    print("No episodes found")
                    return None, None

                # Use first episode to get source list
                vid_id = re.search(r'/detail/(\d+)', site).group(1)
                ep_num = re.search(r'ep(\d+)\.html', links[0]).group(1)
                sources = Dramasq._Get_Sources(vid_id, ep_num)

                if not sources:
                    print("No sources found")
                    return None, None

                name = Dramasq._Prompt_Source(sources, TMP)
                if name is None:
                    return None, None

                Dramasq._selected_source_name = name
                return FileNameClean(title), links
            else:
                return FileNameClean(title), 2

        else:
            # Episode page: /vodplay/{id}/ep{N}.html
            # Title format: "{name} 第{N}集 - DramasQ線上看"
            title = re.sub(r'\s*-\s*DramasQ.*', '', raw_title).strip()

            if get_link:
                m = re.search(r'/vodplay/(\d+)/ep(\d+)', site)
                if not m:
                    return None, None
                vid_id, ep_num = m.group(1), m.group(2)
                sources = Dramasq._Get_Sources(vid_id, ep_num)

                if not sources:
                    print("No sources found")
                    return None, None

                if Dramasq._selected_source_name is None:
                    name = Dramasq._Prompt_Source(sources, TMP)
                    if name is None:
                        return None, None
                    Dramasq._selected_source_name = name

                # Look up by name — order may differ per episode
                src_name = Dramasq._selected_source_name
                matched = [(s, u) for s, u in sources if s == src_name]
                if not matched:
                    print(f"Warning: source '{src_name}' not available for this episode, using first available")
                    matched = sources[:1]
                m3u8_url = matched[0][1]

                chunklist = Dramasq._Fetch_Chunklist(m3u8_url, TMP)
                return FileNameClean(title), chunklist
            else:
                return FileNameClean(title), 1

    def Download_Request(site, TMP, downloadPath, max_threads=15):
        tmpPath = TMP + '/gimy'
        tmpfile = tmpPath + '/0.m3u8'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        title, chunks = Dramasq.Get_Title_Link(site)
        if not chunks or not title:
            print("Connection Failed. Source may be invalid!")
            if DEBUG: print(f"Debug: title='{title}', chunks='{chunks}'\n")
            return False
        print(title)

        if Download_Chunks(chunks, TMP):
            return False

        if MP4convert(tmpfile, downloadPath + '/' + title + '.mp4'):
            return False

        shutil.rmtree(tmpPath)
        return True
