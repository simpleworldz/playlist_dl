# encoding=utf-8
# python3

import base64
import binascii
import hashlib
import json
import os
import time

import requests
from Cryptodome.Cipher import AES

from .tools import download_album_pic, download_music_file, modify_mp3
from . import tools
MODULUS = ('00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7'
           'b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280'
           '104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932'
           '575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b'
           '3ece0462db0a22b8e7')
PUBKEY = '010001'
NONCE = b'0CoJUm6Qyw8W8jud'


def encrypted_id(id):
    magic = bytearray('3go8&$8*3*3h0k(2)2', 'u8')
    song_id = bytearray(id, 'u8')
    magic_len = len(magic)
    for i, sid in enumerate(song_id):
        song_id[i] = sid ^ magic[i % magic_len]
    m = hashlib.md5(song_id)
    result = m.digest()
    result = base64.b64encode(result).replace(b'/', b'_').replace(b'+', b'-')
    return result.decode('utf-8')


def encrypted_request(text):
    # type: (str) -> dict
    data = json.dumps(text).encode('utf-8')
    secret = create_key(16)
    params = aes(aes(data, NONCE), secret)
    encseckey = rsa(secret, PUBKEY, MODULUS)
    return {'params': params, 'encSecKey': encseckey}


def aes(text, key):
    pad = 16 - len(text) % 16
    text = text + bytearray([pad] * pad)
    encryptor = AES.new(key, 2, b'0102030405060708')
    ciphertext = encryptor.encrypt(text)
    return base64.b64encode(ciphertext)


def rsa(text, pubkey, modulus):
    text = text[::-1]
    rs = pow(int(binascii.hexlify(text), 16),
             int(pubkey, 16), int(modulus, 16))
    return format(rs, 'x').zfill(256)


def create_key(size):
    return binascii.hexlify(os.urandom(size))[:16]


fake_headers = {
    # 'Cookie': 'appver=1.5.2',
    'Accept': '*/*',
    'Accept-Encoding': 'gzip,deflate,sdch',
    'Accept-Language': 'zh-CN,zh;q=0.8,gl;q=0.6,zh-TW;q=0.4',
    'Connection': 'keep-alive',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Host': 'music.163.com',
    'Referer': 'http://music.163.com/search/',
    'X-Real-IP': '27.38.4.87',
    'Cookie': 'os=ios',      # 不知道为什么加了这一句，就可以下载一些歌了
    'User-Agent': ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)'
                       ' Ubuntu Chromium/56.0.2924.76 Chrome/56.0.2924.76 Safari/537.36')
}

#  __remember_me=true;_iuqxldmzr_=32; appsign=true; websign=true;


class NetEase(object):
    session = requests.Session()
    csrf = ''

    def __init__(self):
        self.set_wait_interval(0)
        self.privilege = {1: 'h', 0: 'm', 2: 'l'}

    def set_playlist_id(self, id):
        '''
            设置歌单id
        '''
        raise ValueError()

    def set_playlist_url(self, url):
        '''
            设置歌单url
        '''
        try:
            self.playlist_id = url.split('playlist?id=')[1]
        except IndexError:
            raise ValueError()

    def get_playlist_detail(self, playlist_id):
        target_url = 'http://music.163.com/weapi/v3/playlist/detail?csrf_token=' + self.csrf
        data = {
            'id': self.playlist_id,
            'offset': 0,
            'total': 'true',
            'limit': 5000,
            'n': 5000,
            'csrf_token': self.csrf
        }
        ret_json = json.loads(self.session.post(target_url, data=encrypted_request(data), headers=fake_headers).text)

        # 获取用户的昵称，用于创建文件夹
        self.user_nickname = ret_json['playlist']['creator']['nickname']
        if(ret_json['code'] == 200):
            return ret_json['playlist']['tracks']
        else:
            tools.logger.log('Error! Code: %d\n' % ret_json['code'], tools.logger.ERROR)
            return ret_json['data']

    def get_quality_by_privilege(self, all_quality):
        '''
            根据原先设置的优先级确定某一首歌曲的码率
        '''
        selected_quality = -1
        for current_br in range(0, len(self.privilege)):
            if all_quality[self.privilege[current_br]]:
                selected_quality = self.privilege[current_br]
                break
        return selected_quality

    def replace_file_name(self, file_name):
        t = ["\\", "/", "*", "?", "<", ">", "|", '"']
        for i in t:
            file_name = file_name.replace(i, '')
        return file_name

    def parse_playlist_detail(self, origin_playlist_detial):
        if origin_playlist_detial is None:
            return {}, {}
        self.songs_detail = {}
        self.download_music_info = {}
        for origin_single_song_detail in origin_playlist_detial:
            single_song_detail = {}
            single_song_detail['title'] = origin_single_song_detail['name'].replace(u'\xa0', u' ').strip()
            single_song_detail['album'] = {}
            single_song_detail['artists'] = ''
            for artist in origin_single_song_detail['ar']:
                single_song_detail['artists'] = single_song_detail['artists'] + artist['name'].strip() + ','
            single_song_detail['artists'] = single_song_detail['artists'][:-1].strip()
            if len(single_song_detail['artists']) > 50:
                # 如果艺术家过多导致文件名过长，则文件名的作者则为第一个艺术家的名字
                tools.logger.log('Song: %s\'s name too long, cut' % single_song_detail['title'], tools.logger.INFO)
                single_song_detail['file_name'] = single_song_detail['artists'].split(',')[0] + ' - ' + single_song_detail['title']
            else:
                single_song_detail['file_name'] = single_song_detail['artists'] + ' - ' + single_song_detail['title']
            single_song_detail['artists'] = single_song_detail['artists'].replace(',', ';').strip()
            single_song_detail['file_name'] = self.replace_file_name(single_song_detail['file_name']).strip()
            single_song_detail['id'] = origin_single_song_detail['id']
            if 'al' in origin_single_song_detail and origin_single_song_detail['al']:
                single_song_detail['album']['picUrl'] = origin_single_song_detail['al']['picUrl']
                single_song_detail['album']['name'] = origin_single_song_detail['al']['name']

            single_song_detail['date'] = str(time.localtime(origin_single_song_detail['publishTime'] / 1000)[0])

            quality = {}
            quality['h'] = origin_single_song_detail['h']['br'] if origin_single_song_detail['h'] else None  # high
            quality['m'] = origin_single_song_detail['m']['br'] if origin_single_song_detail['m'] else None  # middle
            quality['l'] = origin_single_song_detail['l']['br'] if origin_single_song_detail['l'] else None  # low
            quality_id = origin_single_song_detail[self.get_quality_by_privilege(quality)]['br']
            if quality_id in self.download_music_info:
                self.download_music_info[quality_id].append(origin_single_song_detail['id'])
            else:
                self.download_music_info[quality_id] = [origin_single_song_detail['id']]

            self.songs_detail[single_song_detail['id']] = single_song_detail

    def get_songs_info(self):
        '''
            获取音乐文件的信息，包括下载地址，在类中自动实现
        '''
        target_url = 'http://music.163.com/weapi/song/enhance/player/url?csrf_token=' + self.csrf
        error_song_ids = []
        for (br, ids) in self.download_music_info.items():
            data = {
                'ids': ids,
                'br': br,
                'csrf_token': self.csrf
            }

            json_ret = json.loads(self.session.post(target_url, data=encrypted_request(data), headers=fake_headers).text)
            if json_ret['code'] == 200:
                json_ret = json_ret['data']
            else:
                tools.logger.log('Error! Code: %s' % json_ret['code'], level=tools.logger.ERROR)
                error_song_ids.append(ids)
                continue
            for single_song_detail in json_ret:
                if single_song_detail['url']:
                    self.songs_detail[single_song_detail['id']]['url'] = single_song_detail['url']
                    if 'md5' in single_song_detail:
                        self.songs_detail[single_song_detail['id']]['md5'] = single_song_detail['md5']
                    else:
                        self.songs_detail[single_song_detail['id']]['md5'] = None
                else:
                    error_song_ids.append(single_song_detail['id'])
                    self.songs_detail[single_song_detail['id']]['url'] = None
        return error_song_ids

    def set_wait_interval(self, interval):
        self.interval = interval

    def download_music(self, music_folder, pic_folder, retrytimes):
        '''
            根据类中的所有歌曲信息，下载歌曲文件以及歌曲专辑封面

        Args:
            music_folder<str>:文件夹，用于存下载的歌曲
            pic_folder<str>:文件夹，用于存下载的歌曲的专辑封面
        '''
        current_song_index = 0
        error_songs = []
        for id in self.songs_detail:
            single_song_detail = self.songs_detail[id]
            file_path = None
            if not single_song_detail['url']:
                error_songs.append(single_song_detail['id'])
                continue
            try:
                current_song_index += 1
                if tools.progressbar_window:
                    tools.progressbar_window.set_playlist_progress(current_song_index, self.playlist_total_song_num)
                file_path = os.path.join(music_folder, single_song_detail['file_name'] + '.mp3')
                tools.logger.log('Donwload song file: %s' % single_song_detail['file_name'], level=tools.logger.INFO)

                download_music_file(single_song_detail['url'],
                                    file_path,
                                    single_song_detail['file_name'] + '.mp3',
                                    file_md5=single_song_detail['md5'],
                                    retrytimes=retrytimes)
            except FileExistsError:
                # 不让程序访问已经有的文件，并且用户没有让overwrite
                # 但是有可能用户在一首歌还没有下载完的时候就终止了程序，导致歌曲不完整，信息也没有填上
                # TODO:Fix it
                pass
            except AssertionError:
                error_songs.append(single_song_detail['id'])
            else:
                if single_song_detail['album']['picUrl']:
                    tools.logger.log('Download album pic: %s' % single_song_detail['file_name'], level=tools.logger.INFO)
                    pic_path = os.path.join(pic_folder, single_song_detail['file_name'] + '.jpg')
                    download_album_pic(single_song_detail['album']['picUrl'], pic_path)
                    single_song_detail['pic_path'] = pic_path
                modify_mp3(file_path, single_song_detail)

            if self.interval:
                time.sleep(self.interval)
            # tools.logger.log('', level=None)

        return error_songs

    def download_playlist(self, music_folder, pic_folder, retrytimes=3):
        '''
            下载歌单，该类的主要func

        Args:
            music_folder<str>:文件夹，用于存下载的歌曲
            pic_folder<str>:文件夹，用于存下载的歌曲的专辑封面
        '''

        origin_playlist_detial = self.get_playlist_detail(self.playlist_id)
        self.parse_playlist_detail(origin_playlist_detial)

        music_folder = os.path.join(music_folder, self.user_nickname + '\\' + self.playlist_id)
        pic_folder = os.path.join(pic_folder, self.user_nickname + '\\' + self.playlist_id)

        if not os.path.exists(music_folder):
            os.makedirs(music_folder)
        if not os.path.exists(pic_folder):
            os.makedirs(pic_folder)

        # 先用新版api来获取歌曲的信息
        error_songs_ids = self.get_songs_info()

        # 用旧版的api获取一些可能因为版权原因而导致无法下载的歌曲
        error_songs_ids = self.get_songs_detail_old_api(error_songs_ids)
        self.playlist_total_song_num = len(self.songs_detail) - len(error_songs_ids)

        # 下载
        error_songs_ids.extend(self.download_music(music_folder, pic_folder, retrytimes))

        # 去重
        error_songs_ids = list(set(error_songs_ids))
        error_songs_detail = []

        for single_error_song_id in error_songs_ids:
            error_songs_detail.append(self.songs_detail[single_error_song_id])
        return error_songs_detail

    def get_songs_detail_old_api(self, songs_id):
        target_url = 'http://music.163.com/weapi/search/pc'

        # TODO:提供品质的选择
        quality_privilege = {1: 'mMusic', 0: 'hMusic', 2: 'lMusic', 3: 'bMusic'}
        error_songs_ids = []
        for song_id in songs_id:
            data = {
                's': str(song_id),
                'limit': 1,
                'type': 1,
                'offset': 0,
            }
            try:
                json_ret = json.loads(self.session.post(target_url, data=encrypted_request(data),
                                                        headers=fake_headers).text)['result']['songs'][0]
            except IndexError:
                tools.logger.log("Can't get song", level=tools.logger.ERROR)
                error_songs_ids.append(song_id)
            music = {}
            for i in range(0, len(quality_privilege)):
                if json_ret[quality_privilege[i]]:
                    music = json_ret[quality_privilege[i]]
                    break
            url = None
            if 'dfsId' in music:
                dfsId = music['dfsId']
            if 'dfsId_str' in music:
                dfsId = music['dfsId_str']
            if music and dfsId:
                url = 'http://p2.music.126.net/%s/%s.jpg.mp3' % (encrypted_id(str(dfsId)), dfsId)
            elif not json_ret['mp3Url'].endswith('==/0.mp3'):
                url = json_ret['mp3Url']
            else:
                error_songs_ids.append(song_id)
                continue
            self.songs_detail[song_id]['url'] = url
            self.songs_detail[song_id]['md5'] = None
        return error_songs_ids
