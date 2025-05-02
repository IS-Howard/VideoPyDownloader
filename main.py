import re
import os
from downloader.anime1 import Anime1
from downloader.gimy import Gimy
from downloader.baha import Baha
from downloader.meiju import Meiju
from downloader.hanju import Hanju
# from downloader.animeOne import AnimeOne
# from downloader.mmov import Mmov

def Get_Config():
    with open('config', 'r') as file:
        contents = file.read()
        download_path_match = re.search(r'Download Path:\s*(.*)', contents) # downloadPath = "C:/Users/"+os.getlogin()+"/Downloads/Video"
        quality_match = re.search(r'Quality:\s*(\d+)', contents)

        # Extract the download path and quality if found
        downloadPath = download_path_match.group(1) if download_path_match else None
        Quality = quality_match.group(1) if quality_match else None

    return downloadPath, Quality

def Get_Link_Type(link):
    if link.find("anime1.me")!=-1: #anime1 0(bad) 3(sn) 4(full)
        return Anime1.Link_Validate(link)
    elif link.find("gimy.su")!=-1 or link.find("gimy.ai")!=-1: #gimy 0(bad) 5(sn) 6(full)
        return Gimy.Link_Validate(link)
    elif link.find("anime1.one")!=-1:
        return AnimeOne.Link_Validate(link) #animeOne 0(bad) 7(sn) 8(full)
    elif link.find("meiju")!=-1:
        return Meiju.Link_Validate(link) #meiju 0(bad) 10(full)
    elif link.find("mmov")!=-1:
        return Mmov.Link_Validate(link) #mmov 0(bad) 11(sn) 12(full)
    elif link.find("321tw.com")!=-1: #hanju 0(bad) 14(full)
        return Hanju.Link_Validate(link)
    else:
        return Baha.Link_Validate(link) #baha 0(bad) 1(sn) 2(full)
    return 0

def Multiple_Download_Select(eps):
    try:
        print(f"總共有{len(eps)}集")
        getall = input("全部下載(y/n): ")
        if getall=='n' or getall=='N':
            st = int(input(f"從第幾集開始?(1~{len(eps)}): "))
            ed = int(input(f"下載到第幾集?({st}~{len(eps)}): "))
            st-=1
        else:
            st=0
            ed=len(eps)
        if not st > ed:
            return st, ed
        else:
            print("Bad")
            return None,None

    except Exception as e:
        print("Error:", str(e))
        return None,None

if __name__=='__main__':

    # config
    TMP = (os.getcwd()+"/Tmp").replace('\\','/')
    downloadPath0, Quality = Get_Config()

    while True:
        print("----------------------------------------")
        print("Baha-完整連結(全部下載)或sn(單集)")
        print("Anime1-頁面網址(全部)或(單集)")
        print("Gimy-頁面網址(全部)或(單集)")
        print("----------------------------------------")
        link = input("輸入:")
        if link=='exit':
            break
        linktype = Get_Link_Type(link)
        if linktype==0:
            continue
        if linktype==1:
            Baha.Download_Request(link, TMP, downloadPath0, Quality)
        elif linktype==2:
            title = Baha.Get_Title(link, False)
            downloadPath = downloadPath0 + '/' + title
            eps = Baha.Parse_Episodes(link)
            try:
                st, ed = Multiple_Download_Select(eps)
                for i in range(st,ed):
                    Baha.Download_Request(eps[i], TMP, downloadPath, Quality)
            except Exception as e:
                print("Error:", str(e))
        elif linktype==3:
            Anime1.Download_Request(link, downloadPath0)
        elif linktype==4:
            title,eps = Anime1.Get_Title_Link(link)
            downloadPath = downloadPath0 + '/' + title + '/'
            try:
                st, ed = Multiple_Download_Select(eps)
                for i in range(st,ed):
                    Anime1.Download_Request(eps[i], downloadPath)
            except Exception as e:
                print("Error:", str(e))
        elif linktype==5:
            Gimy.Download_Request(link, TMP, downloadPath0)
        elif linktype==6:
            title, eps = Gimy.Get_Title_Link(link)
            downloadPath = downloadPath0 + '/' + title + '/'
            try:
                st, ed = Multiple_Download_Select(eps)
                for i in range(st,ed):
                    Gimy.Download_Request(eps[i], TMP, downloadPath)
            except Exception as e:
                print("Error:", str(e))
        elif linktype==7:
            sel = int(input(f"選擇分流(1~5): "))
            AnimeOne.Download_Request(link,TMP,downloadPath0, sel)
        elif linktype==8:
            title, eps = AnimeOne.Get_Title_Link(link)
            downloadPath = downloadPath0 + '/' + title + '/'
            try:
                st, ed = Multiple_Download_Select(eps)
                sel = int(input(f"選擇分流(1~5): "))
                for i in range(st,ed):
                    AnimeOne.Download_Request(eps[i], TMP, downloadPath, sel)
            except Exception as e:
                print("Error:", str(e))
        elif linktype==10:
            try:
                title, eps = Meiju.Get_Title_Link(link)
                downloadPath = downloadPath0 + '/' + title + '/'
                st, ed = Multiple_Download_Select(eps)
                for i in range(st,ed):
                    Meiju.Download_Request(eps[i], title+f" 第{i+1}集", TMP, downloadPath)
            except Exception as e:
                print("Error:", str(e))
        elif linktype==11:
            Mmov.Download_Request(link, TMP, downloadPath0)
        elif linktype==12:
            title, eps = Mmov.Get_Title_Link(link)
            downloadPath = downloadPath0 + '/' + title + '/'
            try:
                st, ed = Multiple_Download_Select(eps)
                for i in range(st,ed):
                    Mmov.Download_Request(eps[i], TMP, downloadPath)
            except Exception as e:
                print("Error:", str(e))
        elif linktype==14:
            try:
                title, eps = Hanju.Get_Title_Link(link)
                downloadPath = downloadPath0 + '/' + title + '/'
                st, ed = Multiple_Download_Select(eps)
                for i in range(st,ed):
                    Hanju.Download_Request(eps[i], title+f" 第{i+1}集", TMP, downloadPath)
            except Exception as e:
                print("Error:", str(e))
        