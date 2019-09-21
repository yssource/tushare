#!/usr/bin/env python
# -*- coding:utf-8 -*- 
"""
龙虎榜数据
Created on 2015年6月10日
@author: Jimmy Liu
@group : waditu
@contact: jimmysoa@sina.cn
"""

import pandas as pd
from pandas.compat import StringIO
from tushare.stock import cons as ct
import numpy as np
import time
import json
import re
import demjson
import lxml.html
from lxml import etree
from tushare.util import dateu as du
from tushare.stock import ref_vars as rv
try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request


def top_list(date = None, retry_count=3, pause=0.001):
    """
    获取每日龙虎榜列表
    Parameters
    --------
    date:string
                明细数据日期 format：YYYY-MM-DD 如果为空，返回最近一个交易日的数据
    retry_count : int, 默认 3
                 如遇网络等问题重复执行的次数 
    pause : int, 默认 0
                重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
    
    Return
    ------
    DataFrame
        code：代码
        name ：名称
        pchange：涨跌幅     
        amount：龙虎榜成交额(万)
        buy：买入额(万)
        bratio：占总成交比例
        sell：卖出额(万)
        sratio ：占总成交比例
        reason：上榜原因
        date  ：日期
    """
    if date is None:
        if du.get_hour() < 18:
            date = du.last_tddate()
        else:
            date = du.today() 
    else:
        if(du.is_holiday(date)):
            return None
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(rv.LHB_URL%(ct.P_TYPE['http'], ct.DOMAINS['em'], date, date))
            text = urlopen(request, timeout=10).read()
            text = text.decode('GBK')
            text = text.split('_1=')[1]
            text = eval(text, type('Dummy', (dict,), 
                                           dict(__getitem__ = lambda s, n:n))())
            text = json.dumps(text)
            text = json.loads(text)
            df = pd.DataFrame(text['data'], columns=rv.LHB_TMP_COLS)
            df.columns = rv.LHB_COLS
            df = df.fillna(0)
            df = df.replace('', 0)
            df['buy'] = df['buy'].astype(float)
            df['sell'] = df['sell'].astype(float)
            df['amount'] = df['amount'].astype(float)
            df['Turnover'] = df['Turnover'].astype(float)
            df['bratio'] = df['buy'] / df['Turnover']
            df['sratio'] = df['sell'] /df['Turnover']
            df['bratio'] = df['bratio'].map(ct.FORMAT)
            df['sratio'] = df['sratio'].map(ct.FORMAT)
            df['date'] = date
            for col in ['amount', 'buy', 'sell']:
                df[col] = df[col].astype(float)
                df[col] = df[col] / 10000
                df[col] = df[col].map(ct.FORMAT)
            df = df.drop('Turnover', axis=1)
        except Exception as e:
            print(e)
        else:
            return df
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def cap_tops(days= 5, retry_count= 3, pause= 0.001):
    """
    获取个股上榜统计数据
    Parameters
    --------
        days:int
                  天数，统计n天以来上榜次数，默认为5天，其余是10、30、60
        retry_count : int, 默认 3
                     如遇网络等问题重复执行的次数 
        pause : int, 默认 0
                    重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
    Return
    ------
    DataFrame
        code：代码
        name：名称
        count：上榜次数
        bamount：累积购买额(万)     
        samount：累积卖出额(万)
        net：净额(万)
        bcount：买入席位数
        scount：卖出席位数
    """
    
    if ct._check_lhb_input(days) is True:
        ct._write_head()
        df =  _cap_tops(days, pageNo=1, retry_count=retry_count,
                        pause=pause)
        if df is not None:
            df['code'] = df['code'].map(lambda x: str(x).zfill(6))
            df = df.drop_duplicates('code')
        return df
    
    
def _cap_tops(last=5, pageNo=1, retry_count=3, pause=0.001, dataArr=pd.DataFrame()):   
    ct._write_console()
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(rv.LHB_SINA_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'], rv.LHB_KINDS[0],
                                               ct.PAGES['fd'], last, pageNo))
            text = urlopen(request, timeout=10).read()
            text = text.decode('GBK')
            html = lxml.html.parse(StringIO(text))
            res = html.xpath("//table[@id=\"dataTable\"]/tr")
            if ct.PY3:
                sarr = [etree.tostring(node).decode('utf-8') for node in res]
            else:
                sarr = [etree.tostring(node) for node in res]
            sarr = ''.join(sarr)
            sarr = '<table>%s</table>'%sarr
            df = pd.read_html(sarr)[0]
            df.columns = rv.LHB_GGTJ_COLS
            dataArr = dataArr.append(df, ignore_index=True)
            nextPage = html.xpath('//div[@class=\"pages\"]/a[last()]/@onclick')
            if len(nextPage)>0:
                pageNo = re.findall(r'\d+', nextPage[0])[0]
                return _cap_tops(last, pageNo, retry_count, pause, dataArr)
            else:
                return dataArr
        except Exception as e:
            print(e)
            

def broker_tops(days= 5, retry_count= 3, pause= 0.001):
    """
    获取营业部上榜统计数据
    Parameters
    --------
    days:int
              天数，统计n天以来上榜次数，默认为5天，其余是10、30、60
    retry_count : int, 默认 3
                 如遇网络等问题重复执行的次数 
    pause : int, 默认 0
                重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
    Return
    ---------
    broker：营业部名称
    count：上榜次数
    bamount：累积购买额(万)
    bcount：买入席位数
    samount：累积卖出额(万)
    scount：卖出席位数
    top3：买入前三股票
    """
    if ct._check_lhb_input(days) is True:
        ct._write_head()
        df =  _broker_tops(days, pageNo=1, retry_count=retry_count,
                        pause=pause)
        return df


def _broker_tops(last=5, pageNo=1, retry_count=3, pause=0.001, dataArr=pd.DataFrame()):   
    ct._write_console()
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(rv.LHB_SINA_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'], rv.LHB_KINDS[1],
                                               ct.PAGES['fd'], last, pageNo))
            text = urlopen(request, timeout=10).read()
            text = text.decode('GBK')
            html = lxml.html.parse(StringIO(text))
            res = html.xpath("//table[@id=\"dataTable\"]/tr")
            if ct.PY3:
                sarr = [etree.tostring(node).decode('utf-8') for node in res]
            else:
                sarr = [etree.tostring(node) for node in res]
            sarr = ''.join(sarr)
            sarr = '<table>%s</table>'%sarr
            df = pd.read_html(sarr)[0]
            df.columns = rv.LHB_YYTJ_COLS
            dataArr = dataArr.append(df, ignore_index=True)
            nextPage = html.xpath('//div[@class=\"pages\"]/a[last()]/@onclick')
            if len(nextPage)>0:
                pageNo = re.findall(r'\d+', nextPage[0])[0]
                return _broker_tops(last, pageNo, retry_count, pause, dataArr)
            else:
                return dataArr
        except Exception as e:
            print(e)
        

def inst_tops(days= 5, retry_count= 3, pause= 0.001):
    """
    获取机构席位追踪统计数据
    Parameters
    --------
    days:int
              天数，统计n天以来上榜次数，默认为5天，其余是10、30、60
    retry_count : int, 默认 3
                 如遇网络等问题重复执行的次数 
    pause : int, 默认 0
                重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
                
    Return
    --------
    code:代码
    name:名称
    bamount:累积买入额(万)
    bcount:买入次数
    samount:累积卖出额(万)
    scount:卖出次数
    net:净额(万)
    """
    if ct._check_lhb_input(days) is True:
        ct._write_head()
        df =  _inst_tops(days, pageNo=1, retry_count=retry_count,
                        pause=pause)
        df['code'] = df['code'].map(lambda x: str(x).zfill(6))
        return df 
 

def _inst_tops(last=5, pageNo=1, retry_count=3, pause=0.001, dataArr=pd.DataFrame()):   
    ct._write_console()
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(rv.LHB_SINA_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'], rv.LHB_KINDS[2],
                                               ct.PAGES['fd'], last, pageNo))
            text = urlopen(request, timeout=10).read()
            text = text.decode('GBK')
            html = lxml.html.parse(StringIO(text))
            res = html.xpath("//table[@id=\"dataTable\"]/tr")
            if ct.PY3:
                sarr = [etree.tostring(node).decode('utf-8') for node in res]
            else:
                sarr = [etree.tostring(node) for node in res]
            sarr = ''.join(sarr)
            sarr = '<table>%s</table>'%sarr
            df = pd.read_html(sarr)[0]
            df = df.drop([2,3], axis=1)
            df.columns = rv.LHB_JGZZ_COLS
            dataArr = dataArr.append(df, ignore_index=True)
            nextPage = html.xpath('//div[@class=\"pages\"]/a[last()]/@onclick')
            if len(nextPage)>0:
                pageNo = re.findall(r'\d+', nextPage[0])[0]
                return _inst_tops(last, pageNo, retry_count, pause, dataArr)
            else:
                return dataArr
        except Exception as e:
            print(e)


def inst_detail(retry_count= 3, pause= 0.001):
    """
    获取最近一个交易日机构席位成交明细统计数据
    Parameters
    --------
    retry_count : int, 默认 3
                 如遇网络等问题重复执行的次数 
    pause : int, 默认 0
                重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
                
    Return
    ----------
    code:股票代码
    name:股票名称     
    date:交易日期     
    bamount:机构席位买入额(万)     
    samount:机构席位卖出额(万)     
    type:类型
    """
    ct._write_head()
    df =  _inst_detail(pageNo=1, retry_count=retry_count,
                        pause=pause)
    if len(df)>0:
        df['code'] = df['code'].map(lambda x: str(x).zfill(6))
    return df  
 

def _inst_detail(pageNo=1, retry_count=3, pause=0.001, dataArr=pd.DataFrame()):   
    ct._write_console()
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(rv.LHB_SINA_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'], rv.LHB_KINDS[3],
                                               ct.PAGES['fd'], '', pageNo))
            text = urlopen(request, timeout=10).read()
            text = text.decode('GBK')
            html = lxml.html.parse(StringIO(text))
            res = html.xpath("//table[@id=\"dataTable\"]/tr")
            if ct.PY3:
                sarr = [etree.tostring(node).decode('utf-8') for node in res]
            else:
                sarr = [etree.tostring(node) for node in res]
            sarr = ''.join(sarr)
            sarr = '<table>%s</table>'%sarr
            df = pd.read_html(sarr)[0]
            df.columns = rv.LHB_JGMX_COLS
            dataArr = dataArr.append(df, ignore_index=True)
            nextPage = html.xpath('//div[@class=\"pages\"]/a[last()]/@onclick')
            if len(nextPage)>0:
                pageNo = re.findall(r'\d+', nextPage[0])[0]
                return _inst_detail(pageNo, retry_count, pause, dataArr)
            else:
                return dataArr
        except Exception as e:
            print(e)

            
def _f_rows(x):
    if '%' in x[3]:
        x[11] = x[6]
        for i in range(6, 11):
            x[i] = x[i-5]
        for i in range(1, 6):
            x[i] = np.NaN
    return x


def get_em_gdzjc(type=True, start=None, end=None):
    """
        获取东方财富网数据中心股东增减持数据
    http://datainterface3.eastmoney.com/EM_DataCenter_V3/api/GDZC/GetGDZC?tkn=eastmoney&cfg=gdzc&secucode=&fx=&sharehdname=&pageSize=50&pageNum=2&sortFields=NOTICEDATE&sortDirec=1&startDate=2016-05-01&endDate=2016-05-15
    Parameters
    --------
    type:bool 增减持 e.g:True:增持, False:减持
    start:string e.g: default today
              公告开始日期 format：YYYY-MM-DD
    end:string e.g: default today
              公告截止日期 format：YYYY-MM-DD

       说明：由于是从网站获取的数据，需要一页页抓取，速度取决于您当前网络速度

    Return
    --------
    DataFrame
        FieldName: SHCode,CompanyCode,SCode,Close,ChangePercent,SName,ShareHdName,FX,ChangeNum,BDSLZLTB,BDZGBBL,JYFS,BDHCGZS,BDHCGBL,BDHCYLTGSL,BDHCYLTSLZLTGB,BDKS,BDJZ,NOTICEDATE
    --------
    TableName: RptShareholdersIncreaseMap
    TotalPage: 6
    SplitSymbol: |
    FieldName: SHCode,CompanyCode,SCode,Close,ChangePercent,SName,ShareHdName,FX,ChangeNum,BDSLZLTB,BDZGBBL,JYFS,BDHCGZS,BDHCGBL,BDHCYLTGSL,BDHCYLTSLZLTGB,BDKS,BDJZ,NOTICEDATE
    Data: []
    """
    dataList = []
    fx = 1 if type else 2
    pageNum = 1
    pageSize = 50
    startDate = start if start else du.today()
    endDate = end if end else du.today()
    columns = []
    splitSymbol = ''
    while 1:
        url = 'http://datainterface3.eastmoney.com/EM_DataCenter_V3/api/GDZC/GetGDZC?tkn=eastmoney&cfg=gdzc&secucode=&fx={}&sharehdname=&pageSize={}&pageNum={}&sortFields=BDJZ&sortDirec=1&startDate={}&endDate={}'.format(fx, pageSize, pageNum, startDate, endDate)
        try:
            # data = urlopen(Request(url), timeout=30).read().decode('gbk')
            data = urlopen(Request(url), timeout=30).read()
        except Exception as e:
            print('!!!Warning!!! {}'.format(str(e)))
            break
        jdata = demjson.decode(data)
        dataList += jdata['Data'][0]['Data']
        if pageNum == 1:
            splitSymbol = jdata['Data'][0]['SplitSymbol']
            totalPage = jdata['Data'][0]['TotalPage']
            columns = jdata['Data'][0]['FieldName'].split(',')
        pageNum += 1
        if pageNum > totalPage:
            break
    df_tmp = pd.DataFrame(dataList, columns=['tmp_col'])
    # columns = ['SHCode', 'CompanyCode', 'SCode', 'Close', 'ChangePercent', 'SName', 'ShareHdName', 'FX', 'ChangeNum', 'BDSLZLTB', 'BDZGBBL', 'JYFS', 'BDHCGZS', 'BDHCGBL', 'BDHCYLTGSL', 'BDHCYLTSLZLTGB', 'BDKS', 'BDJZ', 'NOTICEDATE']
    df = pd.DataFrame(df_tmp.tmp_col.str.split(splitSymbol).tolist(), columns=columns)
    df = df.fillna(0)
    # df = df.replace(r'', np.nan, regex=True)
    df = df.replace('', 0)
    df['Close'] = df['Close'].astype(float)
    df['ChangePercent'] = df['ChangePercent'].astype(float)
    df['ChangeNum'] = df['ChangeNum'].astype(float)
    df['BDSLZLTB'] = df['BDSLZLTB'].astype(float)
    df['BDZGBBL'] = df['BDZGBBL'].astype(float)
    df['BDHCGZS'] = df['BDHCGZS'].astype(float)
    df['BDHCGBL'] = df['BDHCGBL'].astype(float)
    df['BDHCYLTGSL'] = df['BDHCYLTGSL'].astype(float)
    df['BDHCYLTSLZLTGB'] = df['BDHCYLTSLZLTGB'].astype(float)
    return df

def get_em_xuangu(q, p=0):
    """
        获取东方财富网数据中心选股公式
    http://xuanguapi.eastmoney.com/Stock/JS.aspx?type=xgq&sty=xgq&token=eastmoney&c=[gfzs7(BK0685)]&p=1&jn=PBSauVYc&ps=40&s=gfzs7(BK0685)&st=1&r=1495854196624
    Parameters
    --------
    type:xgq
    sty:xgq
    token:eastmoney
    c:[gfzs7(BK0685)]
    p:1
    jn:PBSauVYc
    ps:40
    s:gfzs7(BK0685)
    st:1
    r:1495854196624
       说明：由于是从网站获取的数据，需要一页页抓取，速度取决于您当前网络速度
    Return
    --------
    Data: []
    """
    dataList = []
    pageNum = 1
    pageCount = 5
    splitSymbol = ','
    while 1:
        url = 'http://xuanguapi.eastmoney.com/Stock/JS.aspx?{}'.format(q)
        url = re.sub(r'&p=\d*&', '&p={}&'.format(pageNum), url)
        try:
            # data = urlopen(Request(url), timeout=30).read().decode('gbk')
            data = urlopen(Request(url), timeout=30).read()
        except Exception as e:
            print('!!!Warning!!! {}'.format(str(e)))
            break

        matched = re.match(b"[^{]*(.*)", data)
        if matched:
            jdata = demjson.decode(matched.group(1))
        dataList += jdata['Results']
        if pageNum == 1:
            pageCount = int(jdata['PageCount'])
            columns = [ 'C_{}'.format(jdata['Results'][0].split(splitSymbol).index(c)) for c in jdata['Results'][0].split(splitSymbol) if jdata['Results'][0] ]
        if p <= pageCount and p == pageNum:
            break
        pageNum += 1
        if pageNum > pageCount:
            break
    df_tmp = pd.DataFrame(dataList, columns=['tmp_col'])
    return pd.DataFrame(df_tmp.tmp_col.str.split(splitSymbol).tolist(),\
                        columns=columns).rename(columns ={'C_1': 'code', 'C_2': 'name'}).\
                        replace(r'', np.nan, regex=True)

def get_em_report(q, p=0):
    """
        获取东方财富网数据中心选股公式
    http://xuanguapi.eastmoney.com/Stock/JS.aspx?type=xgq&sty=xgq&token=eastmoney&c=[gfzs7(BK0685)]&p=1&jn=PBSauVYc&ps=40&s=gfzs7(BK0685)&st=1&r=1495854196624
    Parameters
    --------
    type:xgq
    sty:xgq
    token:eastmoney
    c:[gfzs7(BK0685)]
    p:1
    jn:PBSauVYc
    ps:40
    s:gfzs7(BK0685)
    st:1
    r:1495854196624
       说明：由于是从网站获取的数据，需要一页页抓取，速度取决于您当前网络速度
    Return
    --------
    Data: []
    """
    dataList = []
    pageNum = 1
    pageCount = 5
    splitSymbol = ','
    while 1:
        url = 'http://xuanguapi.eastmoney.com/Stock/JS.aspx?{}'.format(q)
        url = re.sub(r'&p=\d*&', '&p={}&'.format(pageNum), url)
        try:
            # data = urlopen(Request(url), timeout=30).read().decode('gbk')
            data = urlopen(Request(url), timeout=30).read()
        except Exception as e:
            print('!!!Warning!!! {}'.format(str(e)))
            break

        matched = re.match(b"[^{]*(.*)", data)
        if matched:
            jdata = demjson.decode(matched.group(1))
        dataList += jdata['Results']
        if pageNum == 1:
            pageCount = int(jdata['PageCount'])
            columns = [ 'C_{}'.format(jdata['Results'][0].split(splitSymbol).index(c)) for c in jdata['Results'][0].split(splitSymbol) if jdata['Results'][0] ]
        if p <= pageCount and p == pageNum:
            break
        pageNum += 1
        if pageNum > pageCount:
            break
    df_tmp = pd.DataFrame(dataList, columns=['tmp_col'])
    return pd.DataFrame(df_tmp.tmp_col.split(splitSymbol).tolist(),\
                        columns=columns).rename(columns ={'C_1': 'code', 'C_2': 'name'}).\
                        replace(r'', np.nan, regex=True)
