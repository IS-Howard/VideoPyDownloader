from utils import *

def TryGetAnyVideo(link, TMP, downloadPath):
    try:
        #path
        tmpPath = TMP+'/gimy'
        tmpfile = tmpPath+'/0.m3u8'
        if not os.path.isdir(tmpPath):
            os.makedirs(tmpPath)
        if not os.path.isdir(downloadPath):
            os.makedirs(downloadPath)
        chunks = []
        title = FileNameClean(input("檔名:"))
        if link.endswith("index.m3u8"):
            res = requests.get(link, timeout=30, headers=global_headers)
            res_text = res.text
            if "#EXT-X-STREAM-INF" in res_text:
                # Handle master playlist
                lines = res_text.split('\n')
                for line in lines:
                    if line.strip() and not line.startswith('#'):
                        sub_url = line.strip()
                        if not sub_url.startswith("http"):
                            base_url = link.rsplit('/', 1)[0]
                            link = base_url + '/' + sub_url
                        else:
                            link = sub_url
                        res = requests.get(link, timeout=30, headers=global_headers)
                        res_text = res.text
                        break
            chunks = Parse_m3u8(TMP, res_text, link)
        else:
            chunks = Get_m3u8_chunklist(link)
        print(title)
        if Download_Chunks(chunks, TMP):
            return False
        #ffmpeg convert
        if MP4convert(tmpfile, downloadPath +'/'+ title + ".mp4"):
            return False
        #remove tmp files
        shutil.rmtree(tmpPath)
        return True
    except:
        print("invalid link")