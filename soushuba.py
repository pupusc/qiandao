# -*- coding: utf-8 -*-
"""
实现搜书吧论坛登入和发布空间动态
"""
import os
import re
import sys
from copy import copy

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import time
import logging
import urllib3
import random
from datetime import datetime, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

ch = logging.StreamHandler(stream=sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

def get_refresh_url(url: str):
    try:
        response = requests.get(url)
        if response.status_code != 403:
            response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        meta_tags = soup.find_all('meta', {'http-equiv': 'refresh'})

        if meta_tags:
            content = meta_tags[0].get('content', '')
            if 'url=' in content:
                redirect_url = content.split('url=')[1].strip()
                logger.info(f"Redirecting to: {redirect_url}")
                return redirect_url
        else:
            logger.error("No meta refresh tag found.")
            return None
    except Exception as e:
        logger.exception(f'An unexpected error occurred: {e}')
        return None

def get_url(url: str):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content, 'html.parser')
    
    links = soup.find_all('a', href=True)
    for link in links:
        if link.text == "搜书吧":
            return link['href']
    return None

class SouShuBaClient:

    def __init__(self, hostname: str, username: str, password: str, questionid: str = '0', answer: str = None,
                 proxies: dict | None = None):
        self.session: requests.Session = requests.Session()
        self.hostname = hostname
        # self.username = username
        self.username = "pupusc"
        # self.password = password
        self.password = "..52t1314.."
        self.questionid = questionid
        self.answer = answer
        self._common_headers = {
            "Host": f"{ hostname }",
            "Connection": "keep-alive",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,cn;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        self.proxies = proxies

    def login_form_hash(self):
        rst = self.session.get(f'https://{self.hostname}/member.php?mod=logging&action=login', verify=False).text
        loginhash = re.search(r'<div id="main_messaqge_(.+?)">', rst).group(1)
        formhash = re.search(r'<input type="hidden" name="formhash" value="(.+?)" />', rst).group(1)
        return loginhash, formhash

    def login(self):
        """Login with username and password"""
        loginhash, formhash = self.login_form_hash()
        login_url = f'https://{self.hostname}/member.php?mod=logging&action=login&loginsubmit=yes' \
                    f'&handlekey=register&loginhash={loginhash}&inajax=1'


        headers = copy(self._common_headers)
        headers["origin"] = f'https://{self.hostname}'
        headers["referer"] = f'https://{self.hostname}/'
        payload = {
            'formhash': formhash,
            'referer': f'https://{self.hostname}/',
            'username': self.username,
            'password': self.password,
            'questionid': self.questionid,
            'answer': self.answer
        }

        resp = self.session.post(login_url, proxies=self.proxies, data=payload, headers=headers, verify=False)
        if resp.status_code == 200:
            logger.info(f'Welcome {self.username}!')
        else:
            raise ValueError('Verify Failed! Check your username and password!')

    def credit(self):
        credit_url = f"https://{self.hostname}/home.php?mod=spacecp&ac=credit&showcredit=1&inajax=1&ajaxtarget=extcreditmenu_menu"
        credit_rst = self.session.get(credit_url, verify=False).text

        # 解析 XML，提取 CDATA
        root = ET.fromstring(str(credit_rst))
        cdata_content = root.text

        # 使用 BeautifulSoup 解析 CDATA 内容
        cdata_soup = BeautifulSoup(cdata_content, features="lxml")
        hcredit_2 = cdata_soup.find("span", id="hcredit_2").string

        return hcredit_2

    def space_form_hash(self):
        rst = self.session.get(f'https://{self.hostname}/home.php', verify=False).text
        formhash = re.search(r'<input type="hidden" name="formhash" value="(.+?)" />', rst).group(1)
        return formhash

    def space(self):
        formhash = self.space_form_hash()
        space_url = f"https://{self.hostname}/home.php?mod=spacecp&ac=doing&handlekey=doing&inajax=1"

        headers = copy(self._common_headers)
        headers["origin"] = f'https://{self.hostname}'
        headers["referer"] = f'https://{self.hostname}/home.php'

        for x in range(5):
            payload = {
                "message": "开心赚银币 {0} 次".format(x + 1).encode("GBK"),
                "addsubmit": "true",
                "spacenote": "true",
                "referer": "home.php",
                "formhash": formhash
            }
            resp = self.session.post(space_url, proxies=self.proxies, data=payload, headers=headers, verify=False)
            if re.search("操作成功", resp.text):
                logger.info(resp)
                logger.info(f'{self.username} post {x + 1}nd successfully!')
                time.sleep(120)
            else:
                logger.warning(resp)
                logger.warning(f'{self.username} post {x + 1}nd failed!')

    def get_comment_form_hash(self):
        """获取评论所需的 formhash"""
        rst = self.session.get(f'https://{self.hostname}/home.php', verify=False).text
        formhash = re.search(r'<input type="hidden" name="formhash" value="(.+?)" />', rst).group(1)
        return formhash

    def fetch_book_list(self):
        """从书单列表获取所有主题"""
        forum_url = f"https://{self.hostname}/forum.php?mod=forumdisplay&fid=40"
        headers = copy(self._common_headers)
        headers["referer"] = f"https://{self.hostname}/forum.php?mod=forumdisplay&fid=40"
        
        resp = self.session.get(forum_url, proxies=self.proxies, headers=headers, verify=False)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # 查找所有主题链接
        topics = []
        topic_links = soup.find_all('a', href=re.compile(r'forum\.php\?mod=viewthread&tid=\d+'))
        
        for link in topic_links:
            href = link['href']
            # 提取 tid
            tid_match = re.search(r'tid=(\d+)', href)
            if tid_match:
                tid = tid_match.group(1)
                title = link.text.strip()
                if title and tid:
                    topics.append({'tid': tid, 'title': title})
        
        logger.info(f'Fetched {len(topics)} topics from book list')
        return topics

    def post_forum_comment(self, message: str, formhash: str, tid: str, fid: str = '40'):
        """在论坛主题下发布评论"""
        comment_url = f"https://{self.hostname}/forum.php?mod=post&infloat=yes&action=reply&fid={fid}&extra=page%3D1&tid={tid}&replysubmit=yes&inajax=1"
        
        headers = copy(self._common_headers)
        headers["origin"] = f'https://{self.hostname}'
        headers["referer"] = f"https://{self.hostname}/forum.php?mod=viewthread&tid={tid}&extra=page%3D1"
        
        payload = {
            "formhash": formhash,
            "handlekey": "register",
            "noticeauthor": "",
            "noticetrimstr": "",
            "noticeauthormsg": "",
            "usesig": "1",
            "subject": "",
            "message": message.encode("GBK")
        }
        
        resp = self.session.post(comment_url, proxies=self.proxies, data=payload, headers=headers, verify=False)
        return resp

    def comments(self):
        """
        每小时评论 5 次，间隔 5 分钟以上，时间在一小时内随机分布
        从书单列表随机挑选主题进行评论
        """
        logger.info(f'Starting comment task for {self.username}...')
        
        # 获取书单列表
        try:
            topics = self.fetch_book_list()
            if not topics:
                logger.warning('No topics found in book list!')
                return
        except Exception as e:
            logger.error(f'Failed to fetch book list: {e}')
            return
        
        # 生成 5 个随机时间点（在一小时内）
        minutes_list = []
        while len(minutes_list) < 5:
            rand_minute = random.randint(0, 55)  # 0-55 分钟之间随机
            # 确保间隔至少 5 分钟
            if all(abs(rand_minute - m) >= 5 for m in minutes_list):
                minutes_list.append(rand_minute)
        
        # 排序以便按时间顺序执行
        minutes_list.sort()
        
        logger.info(f'Scheduled comment times: {minutes_list} minutes')
        
        formhash = self.get_comment_form_hash()
        
        # 评论内容列表（可以自定义）
        comment_messages = [
            "谢谢楼主分享，祝搜书吧越办越好！",
            "这本书真不错，感谢分享！",
            "楼主好人一生平安！",
            "下载了，谢谢分享！",
            "找了好久，终于找到了，感谢！",
            "很好的资源，支持一下！",
            "感谢楼主无私奉献！",
            "已收藏，谢谢分享！",
            "楼主万岁，感激不尽！",
            "非常好的书，谢谢分享！"
        ]
        
        base_time = datetime.now()
        selected_topics = []
        
        for i, minute_offset in enumerate(minutes_list):
            # 计算目标时间
            target_time = base_time + timedelta(minutes=minute_offset)
            
            # 等待到目标时间
            wait_seconds = (target_time - datetime.now()).total_seconds()
            if wait_seconds > 0:
                logger.info(f'Waiting {wait_seconds:.0f} seconds until next comment...')
                time.sleep(wait_seconds)
            
            # 随机选择一个主题（避免重复）
            available_topics = [t for t in topics if t['tid'] not in selected_topics]
            if not available_topics:
                selected_topics = []  # 重置
                available_topics = topics
            
            selected_topic = random.choice(available_topics)
            selected_topics.append(selected_topic['tid'])
            
            logger.info(f"Selected topic: {selected_topic['title']} (TID: {selected_topic['tid']})")
            
            # 发布评论
            message = comment_messages[i % len(comment_messages)]
            resp = self.post_forum_comment(message, formhash, selected_topic['tid'])
            
            # 检查是否成功（解析 XML 响应）
            if re.search(r"succeedhandle_register", resp.text):
                logger.info(f'{self.username} comment {i + 1}/5 successfully at {datetime.now().strftime("%H:%M:%S")} on topic "{selected_topic["title"]}"')
            else:
                logger.warning(f'{self.username} comment {i + 1}/5 failed at {datetime.now().strftime("%H:%M:%S")}')
                logger.warning(f'Response: {resp.text[:200]}')
            
            # 每次评论后至少等待 5 分钟
            if i < len(minutes_list) - 1:
                sleep_time = random.randint(300, 360)  # 5-6 分钟
                logger.info(f'Waiting {sleep_time} seconds before next comment...')
                time.sleep(sleep_time)
        
        logger.info(f'Comment task completed for {self.username}!')

if __name__ == '__main__':
    try:
        redirect_url = get_refresh_url('http://' + os.environ.get('SOUSHUBA_HOSTNAME', 'www.soushu2035.com'))
        time.sleep(2)
        redirect_url2 = get_refresh_url(redirect_url)
        url = get_url(redirect_url2)
        logger.info(f'{url}')
        client = SouShuBaClient(urlparse(url).hostname,
                                os.environ.get('SOUSHUBA_USERNAME', "USERNAME"),
                                os.environ.get('SOUSHUBA_PASSWORD', "PASSWORD"))
        client.login()
        client.space()
        client.comments()
        credit = client.credit()
        logger.info(f'{client.username} have {credit} coins!')
    except Exception as e:
        logger.error(e)
        sys.exit(1)
