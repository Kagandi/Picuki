#!/usr/bin/env python3
"""
main.py CLI - Handler
merge dgzr/in-picuki -> motebaya/picuki
20.06.2023 - 8:00 PM 
"""

from lib.Picuki import Picuki
from lib.logger import logging, logger
from argparse import ArgumentParser, RawTextHelpFormatter
from typing import Dict, List
import json
from rich.console import Console
from rich.panel import Panel
from ssl import SSLWantReadError
from aiohttp import ClientSession
from pathlib import Path as PosixPath
from humanize import naturalsize as get_natural_sizes
import pdb
import aiofiles, asyncio, os, re, random, time
from rich.progress import (
    Progress, 
    SpinnerColumn, 
    BarColumn, 
    TextColumn, 
    DownloadColumn, 
    TransferSpeedColumn, 
    TimeRemainingColumn
)

def get_valid_filename(url: str) -> str:
    """
    get filename from string url, exit if can't find it
    """
    if (basename := re.search(r"^https?\:\/\/[^<]+\/q\/(?P<filename>[^\"].*?)\|\|", url)):
        basename = list(basename.groupdict().get('filename')[:25])
        random.shuffle(basename)
        basename = "".join(basename)
        return basename
    logger.warning(f"Cannot find spesific name from url: {url}")
    raise ValueError(
        "invalid url"
    )
    

# async with aiofiles.open('filename', mode='r') as f:
#     async for line in f:
#         print(line)

async def save_json(**kwargs: Dict[str, str]) -> None:
    content = kwargs.get('content')
    fname = kwargs.get('fname')

    media_type = kwargs.get('type')
    output = get_output_path(**kwargs)
    # username = kwargs.get('username')

    filename = os.path.join(
        f"{output}/{media_type}",
        fname
    )
    async with aiofiles.open(filename, "w") as f:
        await f.write(
            json.dumps(content)
        )
        await f.close()
    Console().print(f"[green] Completed..saved as: [blue]{filename}")
        

async def _download(**kwargs: Dict[str, str]) -> None:
    """
    url: str = set url to download
    output: str = set custom output base folder e.g: 
        /media/run/disk/<username>
    filename: str
    """
    url = kwargs.get('url')
    assert url is not None, "stopped, nothing url to download!"

    media_type = kwargs.get('type')
    output = get_output_path(**kwargs)
    
    filename = os.path.join(
        f"{output}/{media_type}",
        get_valid_filename(
            url
        )
    )
    async with ClientSession(headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        }) as session:
        async with session.get(url) as response:
            extension = response.headers.get('Content-Type')
            if not extension:
                raise ValueError(
                    f"Cannot get mimetype of content: {url}"
                )

            filename = "{}.{}".format(filename, extension.split('/')[-1])
            if not os.path.exists(filename):
                async with aiofiles.open(filename, "wb") as f:
                    with Progress(
                        SpinnerColumn(speed=1.5),
                        TextColumn("[green] Downloading..", justify="right"),
                        BarColumn(),
                        "[progress.percentage]{task.percentage:>3.0f}%",
                        DownloadColumn(
                            binary_units=False
                        ),
                        TransferSpeedColumn(),
                        TimeRemainingColumn(),
                        console=Console(),
                        transient=True
                    ) as progress:
                        task = progress.add_task(
                            "[green] Downloading..", total=int(response.headers.get('content-length', 0))
                        )
                        async for content in response.content.iter_chunks():
                            await f.write(
                                content[0]
                            )
                            progress.update(
                                task, advance=len(content[0])
                            )
                        await f.close()
                        progress.stop()
                Console().print(f"[green] Completed..saved as: [blue]{filename}")
            else:
                Console().print(f"[green] SKipping.. [blue]{filename} [green] file exist!")

def get_output_path(**kwargs):
    # pdb.set_trace()
    output = os.path.join(os.path.realpath(kwargs.get(
        'output',
        './'
    )), kwargs.get(
        'username',
        'picuki_media'
    ))
    if not os.path.exists(output):
        try:
            os.makedirs(output)
            for folder in ('images', 'videos', 'thumbnails', 'profile', 'content'):
                folder_path = os.path.join(output, folder)
                if not os.path.exists(folder_path):
                    os.mkdir(folder_path)
        except PermissionError:
            logger.warning(
                f"Directory output: {output} is not writeable!"
            )
            exit(1)
    return output

def show_table(data: Dict[str, str], title: str = None) -> None:
    """
    show profile data
    """
    Console().print(
        Panel.fit(
            '\n'.join(map(
                lambda x: f"[bold]{x[0]}:[/bold] {x[1]}",
                dict(sorted(
                    data.items()
                )).items()
            )), 
            title="information" if not title else title,
            border_style="blue"
        )
    )

def calculate_result(username: str) -> None:
    """
    show all size and total file
    """
    total_size: Dict[str, int] = {
        "total": 0,
        "images": 0,
        "videos": 0,
        "thumbnails": 0
    }
    total: int = 0
    fullpath = os.path.realpath(username)
    for glob in PosixPath(fullpath).glob("*"):
        dirs_list = list(glob.iterdir())
        for filename in dirs_list:
            total_size[glob.name] += filename.stat().st_size
            total_size['total'] += filename.stat().st_size
        
        total += len(dirs_list)
        total_size[glob.name] = "{} / {} files".format(
            get_natural_sizes(
                total_size[glob.name]
            ), str(len(dirs_list)))

    total_size['total'] = "{} / {} files".format(
        get_natural_sizes(
            total_size['total']
        ),
        total
    )
    show_table(
        total_size,
        f"total size: {username}"
    )

async def _main(**kwargs):
    """
    main: CLI handler
    """
    sleep = kwargs.get('sleep')
    output_folder = kwargs.get('output')
    if not kwargs.get('verbose'):
        logging.getLogger().setLevel(logging.INFO)
    
    module = Picuki()
    username = module.clear_username(
        kwargs.get('username')
    )

    selected: List[str] = ['images', 'videos', 'thumbnails']
    if not kwargs.get('all'):
        for select in selected:
            if not kwargs.get(select):
                selected.remove(
                    select
                )

    if (profile := await module.get_profile(username)):
        page, result = profile
        await save_json(content=result, fname=f"{username}.json", type="profile", output=output_folder)
        show_table(result)

        await module.get_media_id(page, logger)
        if len(module.media_id) != 0:
            logger.info(f"Total Media Collected: {len(module.media_id)}")
            logger.info(f"Selected media: {selected}, starting download..")
            for index, media in enumerate(module.media_id, 1):
                logger.info(f"getting content from: {media} [{index} of {len(module.media_id)}]")
                try:
                    if (content := await module.get_media_content(media)):
                        _media = content.pop('media')
                        show_table(content)
                        # pdb.set_trace()
                        await save_json(content={**content, **_media}, fname=f"{media}.json", type="content", output=output_folder)
                    
                        if 'images' in selected:
                            if len(_media['images']) != 0:
                                logger.info(f"Total images collected: {len(_media.get('images'))}")
                                for index, img in enumerate(_media.get('images'), 1):
                                    logger.info(f"downloading images ( {index} of {len(_media.get('images'))})")
                                    await _download(
                                        url=img,
                                        username=username,
                                        type="images",
                                        output=output_folder
                                    )
                            else:
                                logger.warning('there no images to download!')
                        
                        if 'videos' in selected or \
                            'thumbnails' in selected:
                            if len(_media.get('videos')) != 0:
                                logger.info(f"Total videos/thumbnails Collected: {len(_media.get('videos'))}")
                                for index, vids in enumerate(_media.get('videos'), 1):
                                    if 'thumbnails' in selected:
                                        logger.info(f"downloading thumbnails ( {index} of {len(_media.get('videos'))})")
                                        await _download(
                                            url=vids.get('thumbnail'),
                                            username=username,
                                            type="thumbnails",
                                            output=output_folder
                                        )

                                    if 'videos' in selected:
                                        logger.info(f"downloading videos ( {index} of {len(_media.get('videos'))})")
                                        await _download(
                                            url=vids.get('url'),
                                            username=username,
                                            type="videos",
                                            output=output_folder
                                        )
                            else:
                                logger.warning("there's no videos or thumbnails to download..")
                        time.sleep(sleep)
                    else:
                        logger.warning(f"cannot get content from media ID: {media}")
                except (asyncio.exceptions.CancelledError, SSLWantReadError) as e:
                    logger.warning(f"Exception: {str(e)}, in media ID: {media}")
                    time.sleep(sleep)
                    continue
            calculate_result(
                username
            )
        else:
            logger.warning(f"The user: {profile.get('username')} don't have any post..")
    else:
        logger.warning(f"cannot find user: @{username}, check again username")


async def _main_tags(**kwargs):
    """
    main: CLI handler
    """
    sleep = kwargs.get('sleep')
    output_folder = kwargs.get('output')
    tag = kwargs.get('tag')
    if not kwargs.get('verbose'):
        logging.getLogger().setLevel(logging.INFO)
    
    module = Picuki()

    selected: List[str] = ['images', 'videos', 'thumbnails']
    if not kwargs.get('all'):
        for select in selected:
            if not kwargs.get(select):
                selected.remove(
                    select
                )

    if (page := await module.search_tags(tag)):



        await module.get_media_id(page, logger)
        if len(module.media_id) != 0:
            logger.info(f"Total Media Collected: {len(module.media_id)}")
            logger.info(f"Selected media: {selected}, starting download..")
            for index, media in enumerate(module.media_id, 1):
                logger.info(f"getting content from: {media} [{index} of {len(module.media_id)}]")
                try:
                    if (content := await module.get_media_content(media)):
                        _media = content.pop('media')
                        show_table(content)
                        await save_json(content={**content, **_media}, fname=f"{media}.json", type="content", output=output_folder, username=tag)
                        username =  module.clear_username(content["name"])
                        if 'images' in selected:
                            if len(_media['images']) != 0:
                                logger.info(f"Total images collected: {len(_media.get('images'))}")
                                for index, img in enumerate(_media.get('images'), 1):
                                    logger.info(f"downloading images ( {index} of {len(_media.get('images'))})")
                                    await _download(
                                        url=img,
                                        username=tag,
                                        type="images",
                                        output=output_folder
                                    )
                            else:
                                logger.warning('there no images to download!')
                        
                        if 'videos' in selected or \
                            'thumbnails' in selected:
                            if len(_media.get('videos')) != 0:
                                logger.info(f"Total videos/thumbnails Collected: {len(_media.get('videos'))}")
                                for index, vids in enumerate(_media.get('videos'), 1):
                                    if 'thumbnails' in selected:
                                        logger.info(f"downloading thumbnails ( {index} of {len(_media.get('videos'))})")
                                        await _download(
                                            url=vids.get('thumbnail'),
                                            username=tag,
                                            type="thumbnails",
                                            output=output_folder
                                        )

                                    if 'videos' in selected:
                                        logger.info(f"downloading videos ( {index} of {len(_media.get('videos'))})")
                                        await _download(
                                            url=vids.get('url'),
                                            username=tag,
                                            type="videos",
                                            output=output_folder
                                        )
                            else:
                                logger.warning("there's no videos or thumbnails to download..")
                        time.sleep(sleep)
                    else:
                        logger.warning(f"cannot get content from media ID: {media}")
                except (asyncio.exceptions.CancelledError, SSLWantReadError) as e:
                    logger.warning(f"Exception: {str(e)}, in media ID: {media}")
                    time.sleep(sleep)
                    continue
            calculate_result(
                username
            )
        else:
            logger.warning(f"The user: {profile.get('username')} don't have any post..")
    else:
        logger.warning(f"cannot find user: @{username}, check again username")


if __name__ == "__main__":
    parser = ArgumentParser(
        description="\t\tPicuki.com\n  [ instagram bulk profile media downloader ]\n\t   based on @github.com/motebaya", 
        formatter_class=RawTextHelpFormatter
    )
    parser.add_argument("-u", "--username", help="specific instagram username", metavar="")
    parser.add_argument("-t", "--tag", help="specific instagram tag", metavar="")
    parser.add_argument("-i", "--images", help="just download all images", action="store_true")
    parser.add_argument("-v", "--videos", help="just download all videos", action="store_true")
    parser.add_argument("-tm", "--thumbnails", help="just download all videos thumbnails", action="store_true")
    parser.add_argument("-a", "--all", help="download all media", action="store_true")
    parser.add_argument("-o", "--output", help="set output path", default=".")
    parser.add_argument("-s", "--sleep", help="sleep between download", default=2, type=int)

    
    opt = parser.add_argument_group("Optional")
    opt.add_argument("-V", "--verbose", help="enable logger debug mode", action="store_true")
    args = parser.parse_args()
    
    if args.username and \
        any([args.images, args.videos, args.thumbnails, args.all, args.verbose]):
        try:
            asyncio.run(_main(
                **vars(args)
            ))
        except (asyncio.exceptions.CancelledError, SSLWantReadError) as e:
            logger.warning(f"Exception: {str(e)}")
    elif args.tag and \
        any([args.images, args.videos, args.thumbnails, args.all, args.verbose]):
        try:
            asyncio.run(_main_tags(
                **vars(args)
            ))
        except (asyncio.exceptions.CancelledError, SSLWantReadError) as e:
            logger.warning(f"Exception: {str(e)}")
    else:
        parser.print_help()
    
    
