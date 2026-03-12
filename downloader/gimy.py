from utils import *
from urllib.parse import urlparse
import json

class Gimy:
    _selected_sid = None  # for gimy.com.tw batch mode (sid cookie value)

    def Link_Validate(site):
        Gimy._selected_sid = None
        title, link = Gimy.Get_Title_Link(site, False)
        if title is None or link is None:
            return 0
        if link == 1:
            return 5
        if link == 2:
            return 6
        return 0

    def _resolve_url(base_url, path):
        if path.startswith('http'):
            return path
        if path.startswith('/'):
            p = urlparse(base_url)
            return f"{p.scheme}://{p.netloc}{path}"
        return '/'.join(base_url.split('/')[:-1]) + '/' + path

    def _Get_M3u8_Url(episode_url, sid=None):
        """Extract m3u8 URL directly via HTTP requests (no browser needed)."""
        clean_url = episode_url.split('#')[0]

        if 'gimyai.tw' in episode_url:
            # var player_data = {..., "url": "https://...m3u8", ...}
            r = requests.get(clean_url, headers=global_headers, timeout=15)
            m = re.search(r'var\s+player_data\s*=\s*(\{.*?\})\s*</script>', r.content.decode('utf-8'), re.DOTALL)
            if not m:
                return None
            data = json.loads(m.group(1).replace('\\/', '/'))
            return data.get('url')

        elif 'gimy.com.tw' in episode_url:
            # Need sid cookie to select source; sid encoded in URL fragment (#sid=N)
            if sid is None:
                frag_m = re.search(r'sid=(\d+)', urlparse(episode_url).fragment)
                sid = int(frag_m.group(1)) if frag_m else (Gimy._selected_sid or 1)
            s = requests.Session()
            s.cookies.set('sid', str(sid), domain='gimy.com.tw')
            r = s.get(clean_url, headers=global_headers, timeout=15)
            m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', r.content.decode('utf-8'), re.DOTALL)
            if not m:
                return None
            data = json.loads(m.group(1).replace('\\/', '/'))
            return data.get('url')

        else:
            # gimytv.io / gimytw.cc: episode page -> /_watch/{id} iframe -> var url = '...'
            r = requests.get(clean_url, headers=global_headers, timeout=15)
            text = r.content.decode('utf-8')
            watch_m = re.search(r'/_watch/(\d+)', text)
            if not watch_m:
                return None
            parsed = urlparse(r.url)
            watch_url = f"{parsed.scheme}://{parsed.netloc}/_watch/{watch_m.group(1)}"
            r2 = requests.get(watch_url, headers=global_headers, timeout=15)
            url_m = re.search(r"var url\s*=\s*['\"]([^'\"]+)['\"]", r2.text)
            return url_m.group(1) if url_m else None

    def _Fetch_Chunklist(m3u8_url, TMP):
        """Fetch m3u8, resolve master playlist if needed, return chunklist."""
        tmpPath = TMP + '/gimy'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        r = requests.get(m3u8_url, headers=global_headers, timeout=30)
        content = r.text
        sub_match = re.search(r'^(?!#)([^\s]+\.m3u8)', content, re.MULTILINE)
        if sub_match:
            sub_url = Gimy._resolve_url(m3u8_url, sub_match.group(1))
            r2 = requests.get(sub_url, headers=global_headers, timeout=30)
            content = r2.text
            m3u8_url = sub_url
        return Parse_m3u8(TMP, content, m3u8_url)

    def Resolution_Check(sources, TMP):
        """Parallel resolution check for all sources.
        sources: list of (name, first_ep_url, sid)
        """
        preview_path = TMP + '/preview'
        if not os.path.isdir(preview_path):
            os.makedirs(preview_path)

        def check_one(i, name, ep_url, sid):
            try:
                m3u8_url = Gimy._Get_M3u8_Url(ep_url, sid)
                if not m3u8_url:
                    return i, '(Invalid)'
                r = requests.get(m3u8_url, headers=global_headers, timeout=10)
                content = r.text
                # Tier 1: exact resolution from master playlist RESOLUTION tag
                res_match = re.search(r'RESOLUTION=(\d+x\d+)', content)
                if res_match:
                    return i, f"({res_match.group(1)})"
                # Tier 2: resolve sub-playlist, download first chunk for size estimate
                sub_match = re.search(r'^(?!#)([^\s]+\.m3u8)', content, re.MULTILINE)
                if sub_match:
                    sub_url = Gimy._resolve_url(m3u8_url, sub_match.group(1))
                    r2 = requests.get(sub_url, headers=global_headers, timeout=10)
                    content = r2.text
                    m3u8_url = sub_url
                chunk_lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('#')]
                if not chunk_lines:
                    return i, '(Invalid)'
                total_chunks = len(chunk_lines)
                first_chunk = Gimy._resolve_url(m3u8_url, chunk_lines[0])
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
            futures = [ex.submit(check_one, i, n, u, s) for i, (n, u, s) in enumerate(sources)]
            for f in concurrent.futures.as_completed(futures):
                i, label = f.result()
                results[i] = label
        return results

    def _Prompt_Source(sources, TMP):
        """Prompt user to select source with optional resolution check. Returns index."""
        res_check = input("檢查畫質(1:是 2:否): ").strip()
        if res_check == '1':
            print("檢查畫質...")
            resolutions = Gimy.Resolution_Check(sources, TMP)
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
        response = requests.get(site.split('#')[0], headers=global_headers, timeout=15)
        final_url = response.url
        parsed_url = urlparse(final_url)
        prefix = f"{parsed_url.scheme}://{parsed_url.netloc}"
        text = response.content.decode('utf-8')
        soup = bs(text, 'html.parser')

        title_tag = soup.find('title')
        title = title_tag.text if title_tag else None
        if not title:
            print("title not found")
            return None, None

        # === gimyai.tw: /detail/{id} series, /play/{id}-{sid}-{ep} single ===
        if 'gimyai.tw' in final_url:
            title = re.sub(r'\s*-\s*Gimy TV.*', '', title).strip()

            if '/detail/' in final_url:
                if not get_link:
                    return FileNameClean(title), 2

                show_id_m = re.search(r'/detail/(\d+)', final_url)
                if not show_id_m:
                    return None, None
                show_id = show_id_m.group(1)

                # Group episode links by sid: /play/{show_id}-{sid}-{nid}.html
                eps_by_sid = {}
                for a in soup.select(f'a[href*="/play/{show_id}-"]'):
                    m = re.match(r'/play/\d+-(\d+)-(\d+)\.html', a['href'])
                    if m:
                        sid, nid = int(m.group(1)), int(m.group(2))
                        if sid not in eps_by_sid:
                            eps_by_sid[sid] = {}
                        eps_by_sid[sid][nid] = prefix + a['href']

                # Build sources from nav-tabs (or from eps_by_sid keys if no tabs)
                tabs = soup.select('.nav.nav-tabs li a')
                if tabs:
                    sources = []
                    for t in tabs:
                        sid_m = re.search(r'con_playlist_(\d+)', t.get('href', ''))
                        if sid_m:
                            sid = int(sid_m.group(1))
                            if sid in eps_by_sid:
                                first_nid = sorted(eps_by_sid[sid].keys())[0]
                                sources.append((t.get_text(strip=True), eps_by_sid[sid][first_nid], sid))
                else:
                    sources = [(f'來源{sid}', eps[sorted(eps.keys())[0]], sid)
                               for sid, eps in sorted(eps_by_sid.items())]

                if not sources:
                    print("No sources found")
                    return None, None

                if len(sources) == 1:
                    sel_idx = 0
                else:
                    sel_idx = Gimy._Prompt_Source(sources, TMP)
                if sel_idx is None:
                    return None, None

                _, _, sel_sid = sources[sel_idx]
                Gimy._selected_sid = sel_sid
                links = [eps_by_sid[sel_sid][nid] for nid in sorted(eps_by_sid[sel_sid].keys())]
                return FileNameClean(title), links

            else:
                # /play/{id}-{sid}-{nid}.html
                if not get_link:
                    return FileNameClean(title), 1
                m3u8_url = Gimy._Get_M3u8_Url(site)
                if not m3u8_url:
                    return None, None
                return FileNameClean(title), Gimy._Fetch_Chunklist(m3u8_url, TMP)

        # === gimy.com.tw: /voddetail/{id} series, /video/{id}-{ep}[#sid=N] single ===
        elif 'gimy.com.tw' in final_url:
            if 'voddetail' in final_url:
                title = re.sub(r'線上看.*', '', title).strip()
                if not get_link:
                    return FileNameClean(title), 2

                containers = [c for c in soup.select('.playlist') if c.select_one('a.gico')]
                sources = []
                for c in containers:
                    name = c.select_one('a.gico').get_text(strip=True)
                    ul = c.find('ul', id=re.compile(r'con_playlist_\d+'))
                    if not ul:
                        continue
                    sid_m = re.search(r'con_playlist_(\d+)', ul.get('id', ''))
                    if not sid_m:
                        continue
                    sid = int(sid_m.group(1))
                    first_a = ul.select_one('li a')
                    if first_a:
                        sources.append((name, prefix + first_a['href'], sid))

                if not sources:
                    print("No sources found")
                    return None, None

                if len(sources) == 1:
                    sel_idx = 0
                else:
                    sel_idx = Gimy._Prompt_Source(sources, TMP)
                if sel_idx is None:
                    return None, None

                Gimy._selected_sid = sources[sel_idx][2]
                sel_container = containers[sel_idx]
                ele_list = sel_container.select('ul li a')
                links = [prefix + x['href'] for x in ele_list]
                lst = [x.get_text() for x in ele_list]
                if len(lst) > 1 and sum(lst[i] >= lst[i+1] for i in range(len(lst)-1)) > len(lst)//2:
                    links.reverse()
                return FileNameClean(title), links

            else:
                # /video/{id}-{ep}.html[#sid=N]
                title = re.sub(r'線上看', '', title).split('|')[0].strip()
                if not get_link:
                    return FileNameClean(title), 1
                m3u8_url = Gimy._Get_M3u8_Url(site)
                if not m3u8_url:
                    return None, None
                return FileNameClean(title), Gimy._Fetch_Chunklist(m3u8_url, TMP)

        # === gimytv.io / gimytw.cc: /voddetail2/{id} series, /eps/{id}-{ep} single ===
        else:
            if 'voddetail2' in site or 'voddetail2' in final_url:
                title = title.split(' - Gimy TV')[0].strip()
                if not get_link:
                    return FileNameClean(title), 2

                yun_name = [x.get_text(strip=True) for x in soup.select('.nav.nav-tabs li a')]
                yun_all = soup.select('.playlist ul')

                sources = []
                for i, ul in enumerate(yun_all):
                    first_a = ul.select_one('li a')
                    if first_a:
                        name = yun_name[i] if i < len(yun_name) else f'來源{i+1}'
                        sources.append((name, prefix + first_a['href'], None))

                if not sources:
                    print("No sources found")
                    return None, None

                if len(sources) == 1:
                    sel_idx = 0
                else:
                    sel_idx = Gimy._Prompt_Source(sources, TMP)
                if sel_idx is None:
                    return None, None

                ele_list = yun_all[sel_idx].find_all('a')
                links = [prefix + x['href'] for x in ele_list]
                lst = [x.get_text() for x in ele_list]
                if len(lst) > 1 and sum(lst[i] >= lst[i+1] for i in range(len(lst)-1)) > len(lst)//2:
                    links.reverse()
                return FileNameClean(title), links

            else:
                # /eps/{id}-{ep}.html
                title = title.split(' - Gimy TV')[0].strip()
                if not get_link:
                    return FileNameClean(title), 1
                m3u8_url = Gimy._Get_M3u8_Url(site)
                if not m3u8_url:
                    return None, None
                return FileNameClean(title), Gimy._Fetch_Chunklist(m3u8_url, TMP)

    def Download_Request(site, TMP, downloadPath, max_threads=15):
        tmpPath = TMP + '/gimy'
        tmpfile = tmpPath + '/0.m3u8'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        title, chunks = Gimy.Get_Title_Link(site)
        if not chunks or not title:
            print(f"Connection Failed. Source may be invalid!")
            if DEBUG: print(f"Debug: title='{title}', chunks='{chunks}'\n")
            return False
        print(title)

        if Download_Chunks(chunks, TMP):
            return False

        if MP4convert(tmpfile, downloadPath + '/' + title + ".mp4"):
            return False

        shutil.rmtree(tmpPath)
        return True
