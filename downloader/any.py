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
            chunks = Parse_m3u8(TMP, res, link)
        else:
            chunks = Get_m3u8_chunklist(link)
        print(title)
        Download_Chunks(chunks, TMP)
        #ffmpeg convert
        if MP4convert(tmpfile, downloadPath +'/'+ title + ".mp4"):
            return False
        #remove tmp files
        shutil.rmtree(tmpPath)
        return True
    except:
        print("invalid link")