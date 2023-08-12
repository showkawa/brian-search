import http  from 'http';

// const fetch = require('node-fetch');
// const Segment = require('segment');
import fetch from 'node-fetch';
import Segment from 'segment';
import { HttpsProxyAgent } from 'https-proxy-agent';
// const { HttpsProxyAgent } = require('https-proxy-agent');

// const proxyUrl = 'http://127.0.0.1:9982';
// const agent = new HttpsProxyAgent(proxyUrl);

const segment = new Segment();
segment.useDefault();

function sendPostLw(requestUrl) {
  const headers = {
    'Host': 'sg.search.yahoo.com',
    'Connection': 'keep-alive',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:107.0) Gecko/20100101 Firefox/107.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
  };

  return fetch(requestUrl, { headers })
    .then((response) => {
      if (!response.ok) {
        throw new Error('访问出错');
      }

      return response.text();
    });
}

function calculateCost(numTokens) {
  const costPerToken = 0.000003;
  const totalCost = numTokens * costPerToken;
  return totalCost;
}

function calculateCosts(numTokens) {
  const costPerToken = 0.000004;
  const totalCost = numTokens * costPerToken;
  return totalCost;
}

function sendPostJson(jsonStr, key) {
  const timeout = 120;
  const headers = {
    'Host': 'api.openai.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:107.0) Gecko/20100101 Firefox/107.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
    'Content-Type': 'application/json;charset=utf-8',
    'Authorization': `Bearer ${key}`,
  };

  return fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers,
    body: jsonStr,
    timeout,
  }).then((response) => {
    if (!response.ok) {
      throw new Error('访问出错');
    }

    return response.json();
  });
}

function getCurrentDate() {
  const currentTimestamp = Date.now();
  const date = new Date(currentTimestamp);
  const formattedTime = date.toISOString().replace(/\.\d+Z$/, '').replace('T', ' ');
  return formattedTime;
}

async function processInstructions(instructionMessage, key) {
  const segList = segment.doSegment(instructionMessage, {
    simple: true,
  });
  const segListResult = segList.join(' ');
  const messageEncode = encodeURIComponent(segListResult);
  const sendUrl = `https://sg.search.yahoo.com/search?p=${messageEncode}&ei=UTF-8`;
  const requestData = await sendPostLw(sendUrl);

  const titleMatches = requestData.match(/aria-label="(.*?)"/g);
  const contentMatches = requestData.match(/<span class=" fc-falcon">(.*?)<\/span>/g);
  const urlMatches = requestData.match(/class="d-ib p-abs t-0 l-0 fz-14 lh-20 fc-obsidian wr-bw ls-n pb-4"><span>(.*?)<\/span><span>/g);

  if (!titleMatches || !contentMatches || !urlMatches) {
    throw new Error('获取问答失败');
  }

  const searchUrls = urlMatches.map((url) => url.replace(/class="d-ib p-abs t-0 l-0 fz-14 lh-20 fc-obsidian wr-bw ls-n pb-4"><span>/, '').replace(/<\/span><span>/, ''));
  const searchTitles = titleMatches.map((title) => title.replace(/aria-label="/, '').replace(/"/, ''));
  const searchContents = contentMatches.map((content) => content.replace(/<span class=" fc-falcon">/, '').replace(/<\/span>/, ''));

  const aggregateArray = [];
  for (let i = 0; i < 3; i++) {
    const index = i + 1;
    const singleContent = searchContents[i];
    const singleTitle = searchTitles[i];
    const singleUrl = searchUrls[i];
    const singleContentCleaned = singleContent.replace(/<.*?>/g, '');
    const singleString = `NUMBER:${index}\nURL:${singleUrl}\nTITLE:${singleTitle}\nCONTENT:${singleContent}`;
    aggregateArray.push(singleString);
  }

  const compiledContents = aggregateArray.join('\n\n');
  const currentDate = getCurrentDate();
  const replyInstruction = `I will give you a question or an instruction. Your objective is to answer my question or fulfill my instruction.\n\nMy question or instruction is: ${instructionMessage}\n\nFor your reference, today's date is ${currentDate}.\n\nIt's possible that the question or instruction, or just a portion of it, requires relevant information from the internet to give a satisfactory answer or complete the task. Therefore, provided below is the necessary information obtained from the internet, which sets the context for addressing the question or fulfilling the instruction. You will write a comprehensive reply to the given question or instruction. Do not include urls and sources in the summary text. If the provided information from the internet results refers to multiple subjects with the same name, write separate answers for each subject:\n\"\"\"\n${compiledContents}\n\"\"\"\nReply in 中文`;

  const postData = JSON.stringify({
    model: 'gpt-3.5-turbo-16k-0613',
    messages: [{ role: 'user', content: replyInstruction }],
    temperature: 0.7,
  });

  const responseData = await sendPostJson(postData, key);

  const choices = responseData.choices[0].message.content;
  const models = responseData.model;
  const tokens = responseData.usage.prompt_tokens;
  const tokensco = responseData.usage.completion_tokens;
  const money = calculateCost(tokens);
  const moneyw = calculateCosts(tokensco);
  const resultMoney = money + moneyw;
  const mmMoney = resultMoney.toFixed(6);

  return {
    code: 200,
    msg: '获取成功',
    model: models,
    total_money: mmMoney,
    message: instructionMessage,
    answer: choices,
  };
}

const server = http.createServer((req, res) => {
  if (req.url === '/search' && req.method === 'POST') {
    let data = '';
    req.on('data', (chunk) => {
      data += chunk;
    });

    req.on('end', () => {
      const { instructionMessage, key } = JSON.parse(data);
      const additionalHints = '是什么？他有什么优势和缺点,请分别列给我。有同类产品吗？请分别列给我他们的比较信息';
      const processedInstruction = instructionMessage + additionalHints;

      processInstructions(processedInstruction, key)
        .then((result) => {
          res.statusCode = 200;
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify(result));
        })
        .catch((error) => {
          console.error(error);
          res.statusCode = 500;
          res.setHeader('Content-Type', 'text/plain');
          res.end('Internal Server Error');
        });
    });
  } else {
    res.statusCode = 404;
    res.setHeader('Content-Type', 'text/plain');
    res.end('Not Found');
  }
});

const port = 80;
server.listen(port, () => {
  console.log(`Server listening on port ${port}`);
});