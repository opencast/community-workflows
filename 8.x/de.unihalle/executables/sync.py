#!/usr/bin/env python3
# Given an input video, a reference video and an output name,
# output a video with padding in the beginning applied so it starts
# synchroneously with the reference video
# Purpose: Synchonize presentation and presenter from capture agents
#          that fail to do so.

# This file passes pycodestyle (formerly pep8)
# Requires at least Python 3.5, Praat and ffmpeg >= 4.2
# apt install praat python3

# Note for Opencast users:
# https://docs.opencast.org/r/9.x/admin/#workflowoperationhandlers/execute-once-woh/
# Commands run by this operation handler must first be included in the
# commands.allowed list in the Execute Service configuration.
#
# Based on
# http://www.dsg-bielefeld.de/dsg_wp/wp-content/uploads/2014/10/video_syncing_fun.pdf
# Thank you, sk (maybe Dr. Spyros Kousidis?)

import sys
import tempfile
import os
import warnings
import subprocess
import getopt
import statistics
import re


# Thank you, joeld
# source: https://stackoverflow.com/a/287944/2683737
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


config = {
    'input': '',
    'reference': '',
    'output': '',
    'mode': 'pad',
    'duration': 240.0,
    'offset': 0.0,
    'audio_container_drift_allowed': 600.0,
    'min_overlap_required': 10.0,
    'max_deviation': 60.0,
    'threshold': 0.5,
    'add_audio_to_padding': True,
    'silent': False
}


def print_warning(message):
    print(bcolors.WARNING + bcolors.UNDERLINE + "Warning:" + bcolors.ENDC +
          "\n" + message + bcolors.ENDC)


def print_header():
    print("Video Sync version 0.0.0-mlu")
    print("Workflow Operation Handler Executer for Opencast")
    print("")
    print("Given 2 input video files, try to synchronize them if they")
    print("both have an audio channel, using a fast approach w/o recoding.")
    print("")
    print("Python version")
    print(sys.version)


def print_usage():
    print("")
    print("Usage:")
    print("  $ sync-files.py -i in -r ref -o out [--duration=120.0]")
    print("                   [--drift=4.0] [--overlap=10.0]")
    print("  # -i --in:  input video will be sent to output with padding, if")
    print("  #           required and possible. Otherwise output will be a")
    print("  #           hardlink of the input video.")
    print("  # -r --ref: reference video to sync against.")
    print("  # -o --out: write padded video to this path. out should have a")
    print("  #           valid video file extension.")
    print("  # -m --mode:Add padding to video (pad) or truncate beginning")
    print("  #           (trunc) or supply values manually (manual). [pad]")
    print("  # duration: when mode is pad or trunc, scan for similiar audio")
    print("  #           signal (cross-correlation) within this time in")
    print("  #           seconds. [120.0]")
    print("  # offset:   when mode is manual, pad video (positive value) or")
    print("  #           truncate video (negative value). [0.0]")
    print("  # drift:    drift allowed between audio and container [60.0]")
    print("  # overlap:  overlap both track's audio should have as a minimum")
    print("  #           in seconds [10.0]")
    print("  # threshold:more than threshold offset required for performing")
    print("  #           any action i.e. if tracks differ less than threshold")
    print("  #           in length the input video is symlinked to output")
    print("  #           and no padding or truncation is performed. [0.3]")
    print("Surplus arguments are interpreted in the above printed order.")
    print("i.e. the folling discouraged usage is also possible:")
    print("  $ sync-files.py -o out.ogv ref.ogv in.ogv")
    print("Options first, arguments last.")
    print("Note: Please only feed me sane video files. For instance, con-")
    print("      tainer timestamps should match video and audio codec times.")
    print("      When using mode=pad, the timebase should be the same.")
    print("Note: Output of padding may not play well in Chrome. You must")
    print("      re-code before delivery.")


def parse_cmd_args(argv):
    global config
    opts, args = getopt.getopt(argv,
                               "si:r:o:m:",
                               ["silent", "in=", "ref=", "out=", "mode=",
                                "duration=", "offset=", "drift=", "overlap=",
                                "threshold="])

    for i, arg in enumerate(args, start=1):
        if i == 1:
            config['input'] = arg
        elif i == 2:
            config['reference'] = arg
        elif i == 3:
            config['output'] = arg
        elif i == 4:
            config['mode'] = arg
        elif i == 5:
            config['duration'] = float(arg)
        elif i == 6:
            config['offset'] = float(arg)
        elif i == 7:
            config['audio_container_drift_allowed'] = float(arg)
        elif i == 8:
            config['min_overlap_required'] = float(arg)
        elif i == 9:
            config['threshold'] = float(arg)

    for opt, arg in opts:
        if opt in ("-s", "--silent"):
            config['silent'] = True
        elif opt in ("-i", "--in"):
            config['input'] = arg
        elif opt in ("-r", "--ref"):
            config['reference'] = arg
        elif opt in ("-o", "--out"):
            config['output'] = arg
        elif opt in ("-m", "--mode"):
            config['mode'] = arg
        elif opt == '--duration':
            config['duration'] = float(arg)
        elif opt == '--offset':
            config['offset'] = float(arg)
        elif opt == '--drift':
            config['audio_container_drift_allowed'] = float(arg)
        elif opt == '--overlap':
            config['min_overlap_required'] = float(arg)
        elif opt == '--threshold':
            config['threshold'] = float(arg)


def apply_defaults():
    global config
    if config['input'] == "":
        print_usage()
        sys_exit_now("Missing input video!")
    if config['reference'] == "":
        print_usage()
        sys_exit_now("Missing reference video!")
    if config['output'] == "":
        print_usage()
        sys_exit_now("Missing output name!")

    if config['duration'] < 1.0:
        print_warning("Cross-correlation over audio < 1.0s. duration=1.0")
        config['duration'] = 1.0
    if config['audio_container_drift_allowed'] < 0.01:
        print_warning("Drift < 0.01. drift=0.01")
        config['audio_container_drift_allowed'] = 0.01
    if config['min_overlap_required'] < 0:
        print_warning("Overlap required < 0. overlap=0")
        config['min_overlap_required'] = 0
    if config['min_overlap_required'] > config['duration'] / 2:
        print_warning("Overlap required > duration / 2. overlap=duration/2")
        config['min_overlap_required'] = config['duration'] / 2
    if not config['mode'] in ('pad', 'trunc', 'manual',
                              'padding', 'truncate', 'man'):
        print_warning("Mode must be either pad for padding the shorter video\n"
                      "or trunc for truncating the longer video or manual for"
                      "\nmanually supplied values. Assume pad.")
        try:
            config['mode'] = {'pad': 'pad', 'trunc': 'trunc',
                              'manual': 'manual', 'padding': 'pad',
                              'truncate': 'trunc',
                              'man': 'manual'}[config['mode']]
        except KeyError:
            config['mode'] = 'pad'

    p = ('--in={} --ref={} --out={} --mode={} --duration={} --offset={} '
         ' --drift={} --overlap={} --threshold={}')
    print(p.format(
        config['input'],
        config['reference'],
        config['output'],
        config['mode'],
        config['duration'],
        config['offset'],
        config['audio_container_drift_allowed'],
        config['min_overlap_required'],
        config['threshold']
    ))


def sys_exit_now(msg: str):
    print(msg)
    sys.exit(msg)


def sys_exit(msg: str):
    os.link(config['input'], config['output'])
    sys_exit_now(msg)


def sys_exit_ok(msg: str):
    os.link(config['input'], config['output'])
    print(msg)
    print_warning(msg)
    sys.exit(0)


def check_python_version():
    if not is_python_compatible():
        print_header()
        sys_exit_now("Error: This script requires Python 3.5 or greater.")


def is_python_compatible():
    return sys.version_info > (3, 5)


def check_ffmpeg_version():
    if not is_ffmpeg_compatible():
        print_header()
        sys_exit_now("Error: This script requires FFmpeg 4.2 or greater.")


def is_ffmpeg_compatible():
    cp = run_subprocess(['ffmpeg', '-version'])
    print(cp.stdout)
    if cp.returncode != 0:
        print_header()
        sys_exit_now("Error: Can't determine ffmpeg version.")
    m = re.search(r'(?<=version )\d\.\d(?:\.\d)?', cp.stdout)
    return tuple(map(int, m.group(0).split('.'))) >= (4, 2)


def call_subprocess(args):
    print(' '.join(args))
    return subprocess.call(args)


def run_subprocess(args):
    print(' '.join(args))
    completed_process = subprocess.run(
        args,
        stdout=subprocess.PIPE,   # python 3.7: capture_output=True
        universal_newlines=True)
    return completed_process


def ff_extract_wave(start: float, duration: float, video_file: str, n: int):
    ffargs = [
        'ffmpeg',
        '-ss',
        str(start),
        '-i',         # input
        video_file,
        '-vn',        # discard video
        '-c:a',       # audio codec
        'pcm_s16le',  # 16bit, signed, little endian, pulse code modulation
        '-ac', '1',   # one audio channel
        '-t',         # duration of output (i.e. end is not converted)
        str(duration),
        'o' + str(n) + '.wav']   # output file name
    return call_subprocess(ffargs)


def ff_probe_container_duration(video_file: str):
    ffargs = [
        'ffprobe',
        '-v',              # verbosity (do not emit warnings)
        'error',
        '-show_entries',   # which datum should be sent to output
        'format=duration',
        '-of',             # some defaults
        'default=noprint_wrappers=1:nokey=1',
        video_file]
    return run_subprocess(ffargs)


def ff_audio_stream_duration(video_file: str):
    ffargs = [
        'ffprobe',
        '-v',                # verbosity (do not emit warnings)
        'error',
        '-select_streams',   # select first audio stream
        'a:0',
        '-show_entries',     # which datum should be sent to output
        'stream=duration',
        '-of',               # some defaults
        'default=noprint_wrappers=1:nokey=1',
        video_file]
    return run_subprocess(ffargs)


def audio_stream_duration(video_file: str):
    cp = ff_audio_stream_duration(video_file)
    print(cp.stdout)
    if cp.returncode != 0:
        sys_exit("Error: ffprobe for track duration on " + video_file + ".")
    return float(cp.stdout)


def extract_waves(tmp: str, start: float,
                  duration: float, video_file_1: str, video_file_2: str):
    statfs = os.statvfs(tmp)
    avail = statfs.f_frsize * statfs.f_bavail
    required = 2 * duration * 48000 * 16/2 + 256
    print("Free space (bytes): " + str(avail))
    print("Required space (estimate, bytes): " + str(required))
    if (required > avail):
        print_warning(
            "Available space (" + str(avail) + " bytes) on " +
            tmp + " might not be enough for output wave files " +
            str(required) + ".")
    os.chdir(tmp)
    if ff_extract_wave(start, duration, video_file_1, 1) != 0:
        sys_exit("Error: Can't extract wave from " + video_file_1 + ".")
    if ff_extract_wave(start, duration, video_file_2, 2) != 0:
        sys_exit("Error: Can't extract wave from " + video_file_2 + ".")


def get_closest_elements(elems):
    """Return the two closest elements from a list sorted in ascending order"""
    e = elems.copy()
    if len(e) == 1:
        return e
    e.sort()
    diffs = [e[i+1] - e[i] for i in range(len(e)-1)]
    min_diff_index = diffs.index(min(diffs))
    return e[min_diff_index:(min_diff_index+2)]


def get_offset(duration: float, video_file_1: str, video_file_2: str):
    """From two audio or video tracks, extract audio as RIFF/WAVE for the use
    with Praat, run Praat and return the offset (delay) between the two files
    in seconds.

    Args:
        duration (float): Audio duration to extract. Set this to the maximum
                          offset you expect + 10s.
        video_file_1 (str): Path to video file 1
        video_file_2 (str): Path to video file 2

    Returns:
        float: Offset between the two tracks
    """
    script_dir = os.path.dirname(os.path.realpath(__file__))
    print("Running from " + script_dir)
    # First, we need to know how long the two audio tracks are
    a1_len = audio_stream_duration(video_file_1)
    a2_len = audio_stream_duration(video_file_2)
    a_len_min = min(a1_len, a2_len)
    # now that we have the minium length of the 2 tracks, remove the extract
    # duraction
    a_len_min = max(a_len_min - duration, 0)

    # By default, we will try to extract 3 chunks/segments from each track:
    #  At 1/5 of the shortest track minus extract duration and
    #  At 1/3 of the shortest track minus extract duration and
    #  At 2/3 of the shortest track minus extract duration
    # However, we may need to shift them, if the track is too short
    segment_start_times = []

    for f in [1/5, 1/3, 2/3]:
        t = a_len_min*f
        if t > a_len_min:
            t = a_len_min
            segment_start_times.append(t)
            print("Last segment: " + str(t))
            break
        print("Segment: " + str(t))
        segment_start_times.append(t)

    segmet_offsets = []

    for start in segment_start_times:
        with tempfile.TemporaryDirectory() as tmp:
            print("Storing wave files to temporary dir " + tmp)
            extract_waves(tmp, start, duration, video_file_1, video_file_2)
            os.chdir(tmp)
            praat_args = [
                'praat',
                '--run',
                '--no-pref-files',
                '--no-plugins',
                script_dir + '/crosscorrelate.praat',
                tmp + '/o1.wav',
                tmp + '/o2.wav',
                str(duration)]
            cp = run_subprocess(praat_args)
            print(cp.stdout)
            if cp.returncode != 0:
                sys_exit("Error: Running Praat for cross-correlation.")
            offset = float(cp.stdout)
            print("Offset is " + str(offset))
            segmet_offsets.append(offset)

    # If we have > 2 offsets, return the avg of those, which are closest
    closest = get_closest_elements(segmet_offsets)
    if (len(closest) == 2):
        if closest[1] - closest[0] > config['max_deviation']:
            sys_exit("Offsets determined on different positions differ"
                     "more than " + config['max_deviation'] + "s.")

        return statistics.mean(closest)


def get_container_duration(video_file_1: str):
    """Get the duration of audio or video files as reported by ffprobe

    Args:
        video_file_1 (str): Path to video file 1

    Returns:
        float: Length in seconds
    """
    cp = ff_probe_container_duration(video_file_1)
    print(cp.stdout)
    if cp.returncode != 0:
        sys_exit("Error: ffprobe for track duration on " + video_file_1 + ".")
    return float(cp.stdout)


def get_container_duration_diff(video_file_1: str, video_file_2: str):
    """Get the difference in duration of two audio or video files as reported
    by ffprobe

    Args:
        video_file_1 (str): Path to video file 1
        video_file_2 (str): Path to video file 2

    Returns:
        float: Difference in length in seconds between the two tracks
    """
    v1_len = get_container_duration(video_file_1)
    v2_len = get_container_duration(video_file_2)

    diff = v2_len - v1_len
    print("container diff: " + str(diff))
    return diff


def get_audio_duration_diff(video_file_1: str, video_file_2: str):
    """Get the difference in duration of two audio or video files as reported
    by ffprobe

    Args:
        video_file_1 (str): Path to video file 1
        video_file_2 (str): Path to video file 2

    Returns:
        float: Difference in length in seconds between the two tracks
    """
    v1_len = audio_stream_duration(video_file_1)
    v2_len = audio_stream_duration(video_file_2)
    diff = v2_len - v1_len
    print("audio diff: " + str(diff))
    return diff


def ff_extract_first_frames(video_file: str, outfile: str):
    ffargs = [
        'ffmpeg',
        '-f',       # Libavfilter input virtual device.
        'lavfi',
        '-i',       # The null audio source returns unprocessed audio frames
        'anullsrc',
        '-i',
        video_file,
        '-t',       # 10/25 = 0.40
        '0.40',
        '-frames:v',
        '10',
        '-pix_fmt',
        'yuv420p',
        '-c:a',
        'aac',
        '-map',     # use original video
        '1:v',
        '-map',     # discard original audio
        '0:a',
        '-shortest',
        outfile]   # output file name
    return call_subprocess(ffargs)


def ff_pad_video(video_file: str, duration: float, outfile: str):
    ffargs = [
        'ffmpeg',
        '-i',
        video_file,
        '-c:v',
        'libx264',
        '-pix_fmt',
        'yuv420p',
        '-shortest',
        '-filter:v',
        'tpad=start_duration=' + str(duration) + ':start_mode=clone',
        '-filter:a',
        'apad=pad_dur=' + str(duration),
        outfile]   # output file name
    return call_subprocess(ffargs)


def ff_recode_video(video_file: str, duration: float, outfile: str):
    duration = round(duration)
    ffargs = [
        'ffmpeg',
        '-i',
        video_file,
        '-c:v',
        'libx264',
        '-pix_fmt',
        'yuv420p',
        '-filter:v',
        'fps=25',
        '-shortest',
        '-t',
        duration,
        outfile]   # output file name
    return call_subprocess(ffargs)


def pad_first_frames(first_frames_file: str, duration: float, outfile: str):
    # Get the length of the first frames file (should be around 1/25= 0.08s)
    duration_first_frames_file = get_container_duration(first_frames_file)
    print("First frames file duration [s]: " + str(duration_first_frames_file))
    duration_minus_existing = duration - duration_first_frames_file
    return ff_pad_video(first_frames_file, duration_minus_existing, outfile)


def mux_padding(video_file: str, video_ref: str, outfile: str):
    ffargs = [
        'ffmpeg',
        '-i',
        video_file,
        '-i',
        video_ref,
        '-map', '0:v',
        '-map', '1:a',
        '-c', 'copy',
        '-pix_fmt',
        'yuv420p',
        '-shortest',
        outfile]   # output file name
    return call_subprocess(ffargs)


def write_concat_file(frame_file: str, video_file: str, outfile: str):
    f = open(outfile, "w")
    f.write("file '" + frame_file + "'\n")
    f.write("file '" + video_file + "'")
    f.close()
    with open(outfile, "r") as fin:
        print(fin.read())


def concat_video(concat_file: str, outfile: str):
    ffargs = [
        'ffmpeg',
        '-safe',
        '0',       # allow files to be stored in absolute paths or remotely
        '-f',
        'concat',
        '-i',
        concat_file,
        '-max_muxing_queue_size',
        '1000',
        '-pix_fmt',
        'yuv420p',
        '-c',
        'copy',
        outfile]   # output file name
    return call_subprocess(ffargs)


def pad_video(padding_s: float,
              video_in: str, video_ref: str, video_out: str,
              mux_audio: bool):
    with tempfile.TemporaryDirectory() as tmp:
        print("Storing padding files to temporary dir " + tmp)
        if ff_extract_first_frames(video_in, tmp + '/f.mp4') != 0:
            sys_exit("Error: Can't extract first frame from " + video_in + ".")
        if pad_first_frames(tmp + '/f.mp4', padding_s, tmp + '/p.mp4') != 0:
            sys_exit("Can't pad for " + padding_s + "s.")
        if mux_audio:
            if mux_padding(tmp + '/p.mp4', video_ref, tmp + '/m.mp4') != 0:
                sys_exit("Can't mux audio " + video_ref +
                         " to " + tmp + '/m.mp4')
        else:
            os.rename(tmp + '/p.mp4', tmp + '/m.mp4')
        write_concat_file(tmp + '/m.mp4', video_in, tmp + '/concat_list.txt')
        if concat_video(tmp + '/concat_list.txt', video_out) != 0:
            sys_exit("Error: Can't concatenate videos.")


def trunc_video(trunc_s: float, video_in: str, video_out: str):
    ffargs = [
        'ffmpeg',
        '-ss',
        str(abs(trunc_s)),
        '-i',
        video_in,
        '-c',
        'copy',
        '-pix_fmt',
        'yuv420p',
        video_out]
    if call_subprocess(ffargs) != 0:
        sys_exit("Error: Can't truncate video.")


def main():
    check_python_version()
    # check_ffmpeg_version()
    parse_cmd_args(sys.argv[1:])
    if not config['silent']:
        print_header()

    apply_defaults()
    mode = config['mode']

    if mode == 'manual':
        offset = config['offset']
        mode = 'pad' if offset >= 0 else 'trunc'
        print("Running in manual mode: Desired operation: " + mode)
    else:
        container_diff = get_container_duration_diff(
                                                     config['input'],
                                                     config['reference'])
        audio_diff = get_audio_duration_diff(config['input'],
                                             config['reference'])
        offset = get_offset(
                            config['duration'],
                            config['input'],
                            config['reference'])

        audio_container_drift = abs(container_diff - audio_diff)

        cross_corr_overlap = config['duration'] - abs(container_diff)

        if audio_container_drift > 5.0:
            print_warning("Drift between the container and the contained "
                          "audio is: \n" + str(audio_container_drift))
        if audio_container_drift > config['audio_container_drift_allowed']:
            sys_exit("There is too much drift between the container and the\n"
                     "contained audio in the two tracks: " +
                     str(audio_container_drift) + "\nDesynchronized.")

        if cross_corr_overlap < config['min_overlap_required']:
            sys_exit("The supplied tracks differ notably in length so that\n"
                     "cross-correlation within " + str(config['duration']) +
                     "s\n is not reliably possible.\nDesynchronized.")

        if abs(offset) > config['duration'] - config['min_overlap_required']:
            sys_exit("The offset calculated by cross-correlation was too high."
                     "\nDesynchronized.")

    ###############################################################
    # Analyze complete
    # Now, let's start padding or truncating
    print("#############################################")
    print("# offset: " + str(offset) + "s #")
    print("# mode:   " + mode + " #")
    print("#############################################")

    if mode == 'trunc':
        if offset >= -config['threshold']:
            sys_exit_ok("Other track needs truncate or no truncate required.\n"
                        "Bye.")
        else:
            trunc_video(offset, config['input'], config['output'])
    elif mode == 'pad':
        if offset <= config['threshold']:
            sys_exit_ok("Other track needs padding or no padding required.\n"
                        "Bye.")
        else:
            pad_video(offset, config['input'], config['reference'],
                      config['output'], config['add_audio_to_padding'])


if __name__ == "__main__":
    main()
