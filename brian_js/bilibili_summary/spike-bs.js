/**
 * spike-bs.js
 *
 * 获取哔哩哔哩视频评论信息并保存为 JSON 文件
 * 使用方法: node spike-bs.js <视频URL>
 */

const axios = require("axios");
const fs = require("fs-extra");
const path = require("path");

// 配置信息
const config = {
  // 请求配置
  request: {
    timeout: 10000,
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      Referer: "https://www.bilibili.com",
      Origin: "https://www.bilibili.com",
    },
  },
  // 输出目录
  outputDir: "./output",
};

// 创建输出目录
fs.ensureDirSync(path.join(__dirname, config.outputDir));

// 从命令行参数获取视频 URL
const videoUrl = process.argv[2];

if (!videoUrl) {
  console.error("请提供哔哩哔哩视频URL");
  console.error("使用方法: node spike-bs.js <视频URL>");
  process.exit(1);
}

/**
 * 主函数
 */
async function main() {
  try {
    console.log(`开始获取视频评论: ${videoUrl}`);

    // 提取视频ID
    const videoId = extractVideoId(videoUrl);
    if (!videoId) {
      throw new Error("无效的哔哩哔哩视频URL");
    }

    console.log(`提取到视频ID: ${videoId}`);

    // 获取视频信息
    const videoInfo = await getVideoInfo(videoId);
    if (!videoInfo) {
      throw new Error("获取视频信息失败");
    }

    console.log(`获取到视频信息: ${videoInfo.title}`);

    // 获取视频评论
    const comments = await getVideoComments(videoInfo.aid);

    console.log(`获取到 ${comments.length} 条评论`);

    // 构建结果数据
    const result = {
      videoId: videoId,
      title: videoInfo.title,
      url: videoUrl,
      aid: videoInfo.aid,
      owner: videoInfo.owner,
      timestamp: new Date().toISOString(),
      comments: comments,
    };

    // 保存结果
    const outputPath = saveToJson(result);
    console.log(`评论已保存到: ${outputPath}`);

    // 输出评论预览
    if (comments.length > 0) {
      console.log("\n评论预览:");
      for (let i = 0; i < Math.min(3, comments.length); i++) {
        const comment = comments[i];
        console.log(`\n[${i + 1}] 用户: ${comment.member.name}`);
        console.log(`类型: ${comment.type}, 点赞: ${comment.likes}`);
        console.log(
          `内容: ${comment.content.substring(0, 100)}${
            comment.content.length > 100 ? "..." : ""
          }`
        );
      }
    }

    console.log("\n处理完成!");
  } catch (error) {
    console.error("获取视频评论失败:", error.message);
    process.exit(1);
  }
}

/**
 * 从URL中提取视频ID
 * @param {string} url - 视频URL
 * @returns {string|null} - 视频ID
 */
function extractVideoId(url) {
  // 匹配BV号
  const bvMatch = url.match(/\/BV([a-zA-Z0-9]+)/);
  if (bvMatch) {
    return "BV" + bvMatch[1];
  }

  // 匹配AV号
  const avMatch = url.match(/\/av(\d+)/);
  if (avMatch) {
    return "av" + avMatch[1];
  }

  return null;
}

/**
 * 获取视频基本信息
 * @param {string} videoId - 视频ID
 * @returns {Promise<Object|null>} - 视频信息
 */
async function getVideoInfo(videoId) {
  try {
    console.log("正在获取视频基本信息...");

    const response = await axios.get(
      `https://api.bilibili.com/x/web-interface/view?bvid=${videoId}`,
      {
        headers: config.request.headers,
        timeout: config.request.timeout,
      }
    );

    if (response.data && response.data.code === 0 && response.data.data) {
      return {
        title: response.data.data.title,
        desc: response.data.data.desc,
        aid: response.data.data.aid,
        cid: response.data.data.cid,
        pubdate: response.data.data.pubdate,
        owner: {
          mid: response.data.data.owner.mid,
          name: response.data.data.owner.name,
        },
      };
    } else {
      console.error("获取视频信息失败:", response.data?.message || "未知错误");
      return null;
    }
  } catch (error) {
    console.error("获取视频信息时出错:", error.message);
    return null;
  }
}

/**
 * 获取视频评论
 * @param {number} aid - 视频AID
 * @returns {Promise<Array>} - 评论数据
 */
async function getVideoComments(aid) {
  try {
    console.log("正在获取视频评论...");

    if (!aid) {
      console.error("无法获取视频的aid");
      return [];
    }

    // 获取评论
    const commentsUrl = `https://api.bilibili.com/x/v2/reply?oid=${aid}&type=1&sort=2&ps=1`;
    console.log(`评论API: ${commentsUrl}`);

    const response = await axios.get(commentsUrl, {
      headers: config.request.headers,
      timeout: config.request.timeout,
    });

    if (!response.data || response.data.code !== 0) {
      console.error("获取评论失败:", response.data?.message || "未知错误");
      return [];
    }

    const comments = [];

    // 提取置顶评论
    if (response.data.data?.upper?.top) {
      const topComment = response.data.data.upper.top;
      console.log("找到UP主置顶评论");
      comments.push(formatComment(topComment, "pinned"));
    }

    // 提取热门评论
    if (response.data.data?.hots && response.data.data.hots.length > 0) {
      console.log(`找到 ${response.data.data.hots.length} 条热门评论`);

      for (const comment of response.data.data.hots) {
        comments.push(formatComment(comment, "hot"));
      }
    }

    // 提取普通评论
    if (response.data.data?.replies && response.data.data.replies.length > 0) {
      console.log(`找到 ${response.data.data.replies.length} 条普通评论`);

      for (const comment of response.data.data.replies) {
        comments.push(formatComment(comment, "normal"));
      }
    }

    return comments;
  } catch (error) {
    console.error("获取视频评论时出错:", error.message);
    return [];
  }
}

/**
 * 格式化评论
 * @param {Object} comment - 原始评论数据
 * @param {string} type - 评论类型
 * @returns {Object} - 格式化后的评论
 */
function formatComment(comment, type) {
  return {
    type: type,
    content: comment.content.message,
    likes: comment.like,
    rpid: comment.rpid,
    time: comment.ctime,
    member: {
      mid: comment.member.mid,
      name: comment.member.uname,
      avatar: comment.member.avatar,
    },
    replies: comment.replies
      ? comment.replies.map((reply) => ({
          content: reply.content.message,
          likes: reply.like,
          rpid: reply.rpid,
          time: reply.ctime,
          member: {
            mid: reply.member.mid,
            name: reply.member.uname,
            avatar: reply.member.avatar,
          },
        }))
      : [],
  };
}

/**
 * 保存结果到JSON文件
 * @param {Object} data - 数据对象
 * @returns {string} - 保存的文件路径
 */
function saveToJson(data) {
  try {
    // 创建文件名
    let filename = data.videoId;

    if (data.title) {
      // 清理文件名
      const safeTitle = data.title
        .replace(/[\\/:*?"<>|]/g, "_")
        .substring(0, 100);

      filename = `${safeTitle}_${data.videoId}`;
    }

    // 生成输出路径
    const outputPath = path.join(
      __dirname,
      config.outputDir,
      `${filename}_comments.json`
    );

    // 保存内容
    fs.writeFileSync(outputPath, JSON.stringify(data, null, 2), "utf8");

    return outputPath;
  } catch (error) {
    console.error("保存内容时出错:", error.message);
    return null;
  }
}

// 运行主函数
main();
