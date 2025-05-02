from utils import *

class Hanju:
    def Link_Validate(site):
        if "content" in site:
            return 0
        rep = requests.get(site,verify=False)
        if "321tw.com" in site and rep.status_code == 200:
            return 14
        return 0

    def Get_Title_Link(site):
        response = requests.get(site)
        response.encoding = 'utf-8'
        soup = bs(response.text, 'html.parser')
        title = soup.title.text
        result = re.search(r'《(.*?)》', title)
        if result:
            title = result.group(1)
        else:
            print("title not found")
            return "", []
        
        yun_all = soup.find_all('div', class_='list')
        sel = input(f"選擇來源(1~{len(yun_all)}): ")
        sel = int(sel)-1
        yun = yun_all[sel]
        links = ["https://321tw.com"+ep.get('href') for ep in yun.select('a')]

        return FileNameClean(title), links

    def Download_Request(link, title, TMP, downloadPath, max_threads=15):
        #path
        tmpPath = TMP+'/gimy'
        tmpfile = tmpPath+'/0.m3u8'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)

        chunks = Get_m3u8_chunklist(link)

        print(title)
        Download_Chunks(chunks, TMP)

        #ffmpeg convert
        if MP4convert(tmpfile, downloadPath +'/'+ title + ".mp4"):
            return False

        #remove tmp files
        shutil.rmtree(tmpPath)
        return True