from utils import *

class Meiju:
    def Link_Validate(site):
        title, link = Meiju.Get_Title_Link(site,False)

        if title==None or link==None:
            print('err: None')
            return 0
        
        if title=='404 not found' or title=='System Error':
            print("err: Bad Page!")
            return 0
        
        if link==1:
            return 9
        
        if link==2:
            return 10
        
        return 0
    
    def Resolution_Check(src_all):
        src_ep1 = []
        for ele_list in src_all:
            src_ep1.append('https://www.meijutt.cc'+ele_list.find('a')['href'])

        m3u8_ep1 = []
        for link in src_ep1:
            try:
                m3u8_ep1.append(Get_m3u8_url(link, retry=0, retry_wait=10))
            except Exception as e:
                m3u8_ep1.append("")
        
        res = []
        for i in range(len(m3u8_ep1)):
            if m3u8_ep1[i] != '':
                Download_sigle_ts(m3u8_ep1[i], TMP, i)
                if not os.path.isfile(TMP+'/preview/'+str(i)+'.ts'):
                    res.append('(Invalid)')
                    continue
                resolution = Get_Video_Resolution(TMP+'/preview/'+str(i)+'.ts')
                res.append(f"(Resolution:{resolution[0]}x{resolution[1]})")
                os.remove(TMP+'/preview/'+str(i)+'.ts')
            else:
                res.append('(Invalid)')
        return res

    def Get_Title_Link(site, get_link=True):
        response = requests.get(site,verify=False)
        soup = bs(response.text, 'html.parser')

        title_tag = soup.find('title')
        title = title_tag.text if title_tag else ''
        if not title:
            print("title not found")
            return None, None


        if "play" not in site:
            # return title with all eps' links
            pattern = r'(.+)在线观看全集'
            match = re.search(pattern, title)
            if not match:
                return None, None
            title = match.group(1)
            if get_link:
                tab = soup.select('[class^="tabs from-tabs"]')
                yun_all = tab[0].select('[class^="playIco"]')
                yun_name = [x.text for x in yun_all]
                src_all = soup.find_all(class_='mn_list_li_movie')
                try:
                    res_check = input(f"檢查畫質(1:是 2:否): ")
                    if res_check == '1':
                        print("檢查畫質...")
                        resolutions = Meiju.Resolution_Check(src_all)
                        showStr = '\n'
                        for i in range(len(yun_name)):
                            showStr += f"{i+1}.{yun_name[i]} {resolutions[i]}\n"
                        print(showStr)
                    else:
                        print('\n'.join([f"{i+1}.{y}" for i, y in enumerate(yun_name, 0)]))
                    sel = input(f"選擇來源(1~{len(yun_all)}): ")
                    sel = int(sel)-1
                    ele_list = src_all[sel]
                    links = ['https://www.meijutt.cc'+x.find('a')['href'] for x in ele_list]
                except  Exception as e:
                    print(str(e))
                    return None, None
            else:
                links = 2
        else:
            # return sigle eq tile and api link
            pattern = r'(.+)免费在线观看.+第(\d+)集'
            match = re.search(pattern, title)
            if not match:
                return None, None
            title = match.group(1)+match.group(2)
            links = Get_m3u8_url(site) if get_link else 1

        return FileNameClean(title), links

    def Download_Request(site, TMP, downloadPath, max_threads=15):
        #path
        tmpPath = TMP+'/gimy'
        tmpfile = tmpPath+'/0.m3u8'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        title, link = Meiju.Get_Title_Link(site)
        if not link or not title:
            print("Connection Failed. Source may be invalid!\n")
            return False
        print(title)

        Download_Chunks(Download_m3u8(link, TMP), TMP)

        #ffmpeg convert
        if MP4convert(tmpfile, downloadPath +'/'+ title + ".mp4"):
            return False

        #remove tmp files
        shutil.rmtree(tmpPath)
        return True