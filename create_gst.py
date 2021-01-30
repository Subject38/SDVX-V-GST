import os
import subprocess
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3, PictureType
from mutagen.mp3 import MP3
from joblib import Parallel, delayed
import shlex
import xml.etree.ElementTree as ET
from pathvalidate import sanitize_filename
import argparse
from pathlib import Path

parser = argparse.ArgumentParser(prog="create_gst")
parser.add_argument("-i input_folder", dest='input', help='Path to contents/data folder', required=True)
parser.add_argument("-o output_folder", dest='output', help='Path to gst folder', required=True)
parser.add_argument("-e encoder_options", dest='options', help="Options to pass to ffmpeg")
parser.add_argument("-j num_jobs", dest='jobs', help='Number of jobs for joblib to run(should be less than or equal to core count)')
args = parser.parse_args()

data_path = Path(args.input)
gst_path = Path(args.output)
encoder_options = args.options if args.options is not None else ''
num_jobs = int(args.jobs) if args.jobs is not None else 1

with open(f'{data_path}/others/music_db.xml', 'rb') as fp:
    bytedata = fp.read()
    strdata = bytedata.decode('shift_jisx0213', errors='replace')
root = ET.fromstring(strdata)
songs = []

def str_to_datestr(s):
     return "-".join((s[:4], s[4:6], s[6:]))

accent_lut = {
    '驩': 'Ø',
    '齲': '♥',
    '齶': '♡',
    '趁': 'Ǣ',
    '騫': 'á',
    '曦': 'à',
    '驫': 'ā',
    '齷': 'é',
    '曩': 'è',
    '䧺': 'ê',
    '骭': 'ü',
    '隍': 'Ü',
    '雋': 'Ǜ',
    '鬻': '♃',
    '鬥': 'Ã',
    '鬆': 'Ý',
    '鬮': '¡',
    '龕': '€',
    '蹙': 'ℱ',
    '頽': 'ä',
}

for data in root.findall('music'):
    mid = data.attrib['id']
    if int(mid) in [1259, 1438]: # Auto paradise lol
        continue
    info = data.find('info')
    if int(info.find('version').text) != 5:
        continue
    title = info.find('title_name').text
    artist = info.find('artist_name').text
    for orig, rep in accent_lut.items():
        title = title.replace(orig, rep)
        artist = artist.replace(orig, rep)
    release_date = str_to_datestr(info.find('distribution_date').text)
    bpm_min = float(info.find('bpm_min').text) / 100.0
    bpm_max = float(info.find('bpm_max').text) / 100.0
    file_prefix = info.find('ascii').text
    if bpm_min == bpm_max:
        bpm = bpm_min
    else:
        bpm = f'{bpm_min}-{bpm_max}'
    max_diff = 1
    for difficulty in data.find('difficulty'):
        # Figure out the actual difficulty
        offset = {
            'novice': 1,
            'advanced': 2,
            'exhaust': 3,
            'infinite': 4,
            'maximum': 5,
        }.get(difficulty.tag)
        if offset is None:
            continue
        if int(difficulty.find('difnum').text) > 0:
            if offset > max_diff:
                lol = None
                try:
                    lol = open(f'{data_path}/music/{mid}_{file_prefix}/jk_{mid}_{offset}_b.png')
                except:
                    continue
                max_diff = offset
    items = [mid, title, artist, file_prefix, max_diff, bpm, release_date]
    songs.append(items)

try:
    os.mkdir(f'{gst_path}')
except:
    pass

def create_entry(song):
    track_no = song[0]
    title = song[1]
    sanitized_title = sanitize_filename(title)
    artist = song[2]
    file_prefix = song[3]
    max_diff = song[4]
    bpm = song[5]
    release_date = song[6]
    folder_path = f'{data_path}/music/{track_no}_{file_prefix}'.replace('\\', '/')
    jacket_file_name = f'{folder_path}/jk_{track_no}_{max_diff}_b.png'
    ffmpeg_command = f'ffmpeg -i {folder_path}/{track_no}_{file_prefix}.s3v {encoder_options} -nostdin "{gst_path}/{track_no} - {sanitized_title}.mp3"'
    subprocess.run(shlex.split(ffmpeg_command))
    try:
        with open(jacket_file_name, 'rb') as h:
            img_data = h.read()
    except:
        with open(f'{data_path}/graphics/jk_dummy_b.png', 'rb') as h:
            img_data = h.read()
    file_ = MP3(f'{gst_path}/{track_no} - {sanitized_title}.mp3', ID3=ID3)
    file_.tags.add(
        APIC(
            encoding=3, # 3 is for utf-8
            mime='image/png', # image/jpeg or image/png
            type=PictureType.COVER_FRONT, 
            desc=u'Cover',
            data=img_data
        )
    )
    file_.save()
    file_ = EasyID3(f'{gst_path}/{track_no} - {sanitized_title}.mp3')
    file_['artist'] = artist
    file_['title'] = title
    file_['date'] = release_date
    file_['tracknumber'] = str(int(track_no))
    file_['album'] = 'SOUND VOLTEX VIVID WAVE GST'
    file_['bpm'] = str(bpm)
    file_.save()

Parallel(n_jobs=num_jobs)(delayed(create_entry)(row) for row in songs)
