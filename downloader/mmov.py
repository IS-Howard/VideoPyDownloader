from utils import *

class Mmov:
    def Link_Validate(site):
        title, link = Mmov.Get_Title_Link(site,False)
        if link==1:
            return 11
        if link==2:
            return 12
        return 0

    def Get_Title_Link(site, get_link=True):
        response = requests.get(site)
        soup = bs(response.text, 'html.parser')

        title_tag = soup.find('title')
        title = title_tag.text if title_tag else ''
        if not title:
            print("title not found")
            return None, None


        if "play" not in site:
            # return title with all eps' links
            pattern = r'(.+)免費線上看'
            match = re.search(pattern, title)
            if not match:
                return None, None
            title = match.group(1)
            if get_link:
                yun_all = soup.select('[class^="stui-content__playlist"]')
                yun_name = [x.parent.find('h3').text for x in yun_all]
                print('\n'.join([f"{i+1}.{y}" for i, y in enumerate(yun_name, 0)]))
                try:
                    sel = input(f"選擇來源(1~{len(yun_all)}): ")
                    sel = int(sel)-1
                    ele_list = yun_all[sel].select('li')
                    links = ['https://www.mmov.app'+x.find('a')['href'] for x in ele_list]
                except  Exception as e:
                    print(str(e))
                    return None, None
            else:
                links = 2
        else:
            title = title.split("-")[0]
            links = Get_m3u8_url(site) if get_link else 1

        return title, links

    def Download_Request(site, TMP, downloadPath, max_threads=15):
        #path
        tmpPath = TMP+'/gimy'
        tmpfile = tmpPath+'/0.m3u8'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        print(site)
        title, link = Mmov.Get_Title_Link(site)
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