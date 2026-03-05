from utils import *
from urllib.parse import urlparse

class Gimy:
    def Link_Validate(site):
        title, link = Gimy.Get_Title_Link(site, False)

        if title is None or link is None:
            print('err: None')
            return 0

        if title == '404 not found' or title == 'System Error':
            print("err: Bad Page!")
            return 0

        if link == 1:
            return 5

        if link == 2:
            return 6

        return 0

    def Resolution_Check(first_eps, wait=10):
        """Check resolution using first episode URL from each source."""
        TMP = (os.getcwd()+"/Tmp").replace('\\','/')
        m3u8_ep1 = []
        for i, link in enumerate(first_eps):
            try:
                if DEBUG: print(f"Debug: Getting m3u8 for source {i}: {link}")
                chunklist = Get_m3u8_chunklist(link, retry=0, retry_wait=wait)
                if DEBUG: print(f"Debug: Got {len(chunklist)} chunks for source {i}")
                m3u8_ep1.append(chunklist)
            except Exception as e:
                if DEBUG: print(f"Debug: Failed to get m3u8 for source {i}: {e}")
                m3u8_ep1.append("")

        res = []
        for i in range(len(m3u8_ep1)):
            if len(m3u8_ep1[i]) > 0:
                try:
                    if not os.path.isdir(TMP+'/preview'):
                        os.makedirs(TMP+'/preview')
                    if DEBUG: print(f"Debug: Downloading chunk for source {i}: {m3u8_ep1[i][0]}")
                    download_chunk(m3u8_ep1[i][0], i, TMP+'/preview', timeout=10, retry=1)
                    if not os.path.isfile(TMP+'/preview/'+str(i)+'.ts'):
                        res.append('(Invalid)')
                        continue
                    file_size = os.path.getsize(TMP+'/preview/'+str(i)+'.ts')
                    if file_size == 0:
                        res.append('(Invalid)')
                        continue
                    quality = Get_Video_Resolution(TMP+'/preview/'+str(i)+'.ts')
                    res.append(f"(Resolution:{quality})")
                except Exception as e:
                    if DEBUG: print(f"Debug: Resolution check failed for source {i}: {e}")
                    res.append('(Invalid)')
            else:
                res.append('(Invalid)')
        return res

    def Get_Title_Link(site, get_link=True):
        response = requests.get(site, headers=global_headers)
        soup = bs(response.text, 'html.parser')

        # Get base URL after redirect (site may redirect to gimytv.io)
        parsed = urlparse(response.url)
        prefix = f"{parsed.scheme}://{parsed.netloc}"

        title_tag = soup.find('title')
        title = title_tag.text if title_tag else None
        if not title:
            print("title not found")
            return None, None

        if 'voddetail' in site:
        # Series/detail page
            if get_link:
                if 'voddetail2' in site:
                    # gimytv.io: source tabs in .nav.nav-tabs, episodes in .playlist ul
                    title = title.split(' - Gimy TV')[0].strip()
                    yun_name = [x.get_text(strip=True) for x in soup.select('.nav.nav-tabs li a')]
                    yun_all = soup.select('.playlist ul')
                    first_eps = [prefix + ul.select_one('li a')['href'] for ul in yun_all if ul.select_one('li a')]

                    def get_links(sel):
                        ele_list = yun_all[sel].find_all('a')
                        links = [prefix + x['href'] for x in ele_list]
                        lst = [x.get_text() for x in ele_list]
                        if sum(lst[i] >= lst[i+1] for i in range(len(lst)-1)) > len(lst)//2:
                            links.reverse()
                        return links
                else:
                    # gimy.com.tw: source name in a.gico, episodes in ul li a with #sid=X
                    title = re.sub(r'線上看.*', '', title).strip()
                    containers = [c for c in soup.select('.playlist') if c.select_one('a.gico')]
                    yun_name = [c.select_one('a.gico').get_text(strip=True) for c in containers]
                    first_eps = [prefix + c.select_one('ul li a')['href'] for c in containers if c.select_one('ul li a')]

                    def get_links(sel):
                        ele_list = containers[sel].select('ul li a')
                        links = [prefix + x['href'] for x in ele_list]
                        lst = [x.get_text() for x in ele_list]
                        if sum(lst[i] >= lst[i+1] for i in range(len(lst)-1)) > len(lst)//2:
                            links.reverse()
                        return links

                try:
                    res_check = input(f"檢查畫質(1:是 2:否): ")
                    if res_check == '1':
                        waitStr = input(f"重新整理時長(秒):")
                        print("檢查畫質...")
                        resolutions = Gimy.Resolution_Check(first_eps, int(waitStr))
                        showStr = '\n'
                        for i in range(len(yun_name)):
                            showStr += f"{i+1}.{yun_name[i]} {resolutions[i]}\n"
                        print(showStr)
                    else:
                        print('\n'.join([f"{i+1}.{y}" for i, y in enumerate(yun_name)]))
                    sel = input(f"選擇來源(1~{len(yun_name)}): ")
                    if not sel.strip():
                        print("未選擇來源")
                        return None, None
                    links = get_links(int(sel)-1)
                except Exception as e:
                    print(str(e))
                    return None, None
            else:
                if 'voddetail2' in site:
                    title = title.split(' - Gimy TV')[0].strip()
                else:
                    title = re.sub(r'線上看.*', '', title).strip()
                links = 2
        else:
        # Single episode page (/eps/... or /video/...)
            if '/eps/' in site:
                title = title.split(' - Gimy TV')[0].strip()
            else:
                # /video/ format: "公益律師線上看第01集 | Gimy劇迷" -> "公益律師第01集"
                title = re.sub(r'線上看', '', title).split('|')[0].strip()
            links = Get_m3u8_chunklist(site) if get_link else 1

        return FileNameClean(title), links

    def Download_Request(site, TMP, downloadPath, max_threads=15):
        #path
        tmpPath = TMP+'/gimy'
        tmpfile = tmpPath+'/0.m3u8'
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

        Download_Chunks(chunks, TMP)

        #ffmpeg convert
        if MP4convert(tmpfile, downloadPath +'/'+ title + ".mp4"):
            return False

        #remove tmp files
        shutil.rmtree(tmpPath)
        return True
