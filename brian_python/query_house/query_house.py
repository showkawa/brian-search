import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

CITY_REGIONS = {
    '深圳': [
        'Futian', 'Luohu', 'Nanshan', 'Yantian', 'Baoan', 'Longgang',
        'Longhua', 'Guangming', 'Pingshan', 'Dapeng'
    ],
    '广州': [
        'Yuexiu', 'Liwan', 'Tianhe', 'Haizhu', 'Baiyun', 'Huangpu',
        'Panyu', 'Huadu', 'Conghua', 'Zengcheng', 'Nansha'
    ],
    '武汉': [
        'Jiang\'an', 'Jianghan', 'Qiaokou', 'Hanyang', 'Wuchang',
        'Hongshan', 'Qingshan', 'Dongxihu', 'Caidian', 'Hannan',
        'Jiangxia', 'Huangpi', 'Xinzhou'
    ],
    '惠州': [
        'Huicheng', 'Huiyang', 'Boluo', 'Huidong', 'Longmen'
    ]
}

URL_TEMPLATE = 'https://sf.taobao.com/list/house?city={city}&region={region}&page={page}'
headers = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/90.0.4430.93 Safari/537.36'
    )
}

def scrape_region(city, region):
    logging.info(f"开始爬取：城市={city}，区域={region}")
    results = []
    page = 1
    while True:
        url = URL_TEMPLATE.format(city=city, region=region, page=page)
        logging.info(f"请求第 {page} 页：{url}")
        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code != 200:
                logging.warning(f"请求失败，状态码: {resp.status_code}")
                break
            soup = BeautifulSoup(resp.text, 'lxml')
            items = soup.select('.list-item')
            if not items:
                logging.info(f"第 {page} 页无数据，结束")
                break
            for item in items:
                try:
                    title = item.select_one('.item-title').get_text(strip=True)
                    price = item.select_one('.reserve-price').get_text(strip=True)
                    date = item.select_one('.auction-date').get_text(strip=True)
                    link = item.select_one('a')['href']
                    results.append({
                        '城市': city,
                        '区域': region,
                        '标题': title,
                        '起拍价': price,
                        '拍卖日期': date,
                        '链接': link
                    })
                except Exception as e:
                    logging.error(f"解析条目出错: {e}")
            page += 1
        except Exception as e:
            logging.error(f"请求失败: {e}")
            break
    logging.info(f"完成爬取：城市={city} 区域={region}，共 {len(results)} 条数据")
    return results

def run_scraper():
    logging.info("爬虫启动")
    all_data = []
    for city, regions in CITY_REGIONS.items():
        for region in regions:
            data = scrape_region(city, region)
            all_data.extend(data)

    if all_data:
        df = pd.DataFrame(all_data)
        now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = f"house_auction_{now}.xlsx"
        df.to_excel(file_name, index=False)
        logging.info(f"数据保存为：{file_name}")
    else:
        logging.warning("未获取到任何数据")
    logging.info("爬虫结束")

if __name__ == '__main__':
    run_scraper()