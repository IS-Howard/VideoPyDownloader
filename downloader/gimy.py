from utils import *

class Gimy:
    def Link_Validate(site):
        title, link = Gimy.Get_Title_Link(site,False)

        if title==None or link==None:
            print('err: None')
            return 0
        
        if title=='404 not found' or title=='System Error':
            print("err: Bad Page!")
            return 0
        
        if link==1:
            return 5
        
        if link==2:
            return 6
        
        return 0

    def Resolution_Check(yun_all, prefix, wait=10):
        TMP = (os.getcwd()+"/Tmp").replace('\\','/')
        src_ep1 = []
        for yun in yun_all:
            ele = yun.find_parent().find_next_sibling().find('a')
            src_ep1.append(prefix + ele['href'])

        m3u8_ep1 = []
        for i, link in enumerate(src_ep1):
            try:
                from utils import DEBUG
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
                    from utils import DEBUG
                    if DEBUG: print(f"Debug: Downloading chunk for source {i}: {m3u8_ep1[i][0]}")
                    download_chunk(m3u8_ep1[i][0], i, TMP+'/preview', timeout=10, retry=1)
                    if not os.path.isfile(TMP+'/preview/'+str(i)+'.ts'):
                        if DEBUG: print(f"Debug: File not found after download: {TMP+'/preview/'+str(i)+'.ts'}")
                        res.append('(Invalid)')
                        continue
                    file_size = os.path.getsize(TMP+'/preview/'+str(i)+'.ts')
                    if DEBUG: print(f"Debug: Downloaded file size: {file_size} bytes")
                    if file_size == 0:
                        if DEBUG: print(f"Debug: Downloaded file is empty")
                        res.append('(Invalid)')
                        continue
                    resolution = Get_Video_Resolution(TMP+'/preview/'+str(i)+'.ts')
                    if DEBUG: print(f"Debug: Resolution: {resolution}")
                    if resolution[0] == 0 and resolution[1] == 0:
                        res.append('(Invalid)')
                    else:
                        res.append(f"(Resolution:{resolution[0]}x{resolution[1]})")
                    # try:
                    #     os.remove(TMP+'/preview/'+str(i)+'.ts')
                    # except:
                    #     pass
                except Exception as e:
                    from utils import DEBUG
                    if DEBUG: print(f"Debug: Resolution check failed for source {i}: {e}")
                    res.append('(Invalid)')
            else:
                res.append('(Invalid)')
        return res

    def Get_Title_Link(site, get_link=True):
        response = requests.get(site)
        soup = bs(response.text, 'html.parser')

        title_tag = soup.find('title')
        title = title_tag.text if title_tag else None
        if not title:
            print("title not found")
            return None, None

        prefix = "https://gimy.ai" if "gimy.ai" in site else "https://gimy.su"
        if "vod" in site:
        # return title with all eps' links
            title = title.split('線上看')[0] #main
            if get_link:
                yun_all = soup.find_all(class_='gico')
                yun_name = [x.text for x in yun_all]
                try:
                    res_check = input(f"檢查畫質(1:是 2:否): ")
                    if res_check == '1':
                        waitStr = input(f"重新整理時長(秒):")
                        print("檢查畫質...")
                        resolutions = Gimy.Resolution_Check(yun_all, prefix, int(waitStr))
                        showStr = '\n'
                        for i in range(len(yun_name)):
                            showStr += f"{i+1}.{yun_name[i]} {resolutions[i]}\n"
                        print(showStr)
                    else:
                        print('\n'.join([f"{i+1}.{y}" for i, y in enumerate(yun_name, 0)]))
                    sel = input(f"選擇來源(1~{len(yun_all)}): ")
                    if not sel.strip():
                        print("未選擇來源")
                        return None, None
                    sel = int(sel)-1
                    yun = yun_all[sel]
                    ele_list =  yun.find_parent().find_next_sibling().find_all('a')
                    links = [prefix+x['href'] for x in ele_list]
                    lst = [x.get_text() for x in ele_list]
                    if sum(lst[i] >= lst[i + 1] for i in range(len(lst) - 1)) > len(lst)//2: #loose decending ordered
                        links.reverse()
                except  Exception as e:
                    print(str(e))
                    return None, None
            else:
                links = 2
        else:
        # return single eq tile and api link
            title = title.replace(" - Gimy 劇迷", "") #ep
            title = title.replace("線上看","")
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
            from utils import DEBUG
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