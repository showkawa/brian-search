#!/usr/bin/env node

/**
 * get_npm_dep.js
 * 
 * 从指定文件中解析每一行内容，提取NPM依赖信息
 * 例如从 `14 verbose stack Error: extraneous: @aashutoshrathi/word-wrap@1.2.6 C:\Users\...`
 * 提取出 `word-wrap@1.2.6`
 * 
 * 使用方法：node get_npm_dep.js <文件路径>
 */

const fs = require('fs');
const path = require('path');

// 获取命令行参数中的文件路径
const filePath = process.argv[2];

if (!filePath) {
  console.error('错误: 请提供文件路径');
  console.error('使用方法: node get_npm_dep.js <文件路径>');
  process.exit(1);
}

// 确保文件存在
if (!fs.existsSync(filePath)) {
  console.error(`错误: 文件不存在: ${filePath}`);
  process.exit(1);
}

// 生成输出文件路径（与输入文件在同一文件夹）
const inputDir = path.dirname(filePath);
const inputFileName = path.basename(filePath, path.extname(filePath));
const outputFilePath = path.join(inputDir, `${inputFileName}_deps.txt`);

// 读取文件内容
fs.readFile(filePath, 'utf8', (err, data) => {
  if (err) {
    console.error(`读取文件出错: ${err.message}`);
    process.exit(1);
  }

  // 按行分割文件内容
  const lines = data.split('\n');
  
  // 存储提取的依赖信息
  const dependencies = [];
  
  // 处理每一行
  lines.forEach(line => {
    // 跳过空行
    if (!line.trim()) return;
    
    // 查找包含依赖信息的行
    if (line.includes('@') && line.includes('C:')) {
      try {
        // 提取@后面、C:前面的内容
        const parts = line.split(' ');
        let packageInfo = null;
        
        // 遍历每个部分，找到包含@的部分并且该部分在C:前面
        for (let i = 0; i < parts.length; i++) {
          if (parts[i].includes('@') && !parts[i].startsWith('C:')) {
            const nextPart = parts[i+1] || '';
            if (nextPart.startsWith('C:')) {
              // 这是我们要找的部分
              const fullPackage = parts[i];
              
              // 从全路径中提取包名和版本
              // 处理形如 @aashutoshrathi/word-wrap@1.2.6 的格式
              const match = fullPackage.match(/(@[^/]+\/)?([^@]+)@([^/]+)/);
              
              if (match) {
                // 使用捕获的组构建输出
                const packageName = match[2];
                const packageVersion = match[3];
                packageInfo = `${packageName}@${packageVersion}`;
              }
              break;
            }
          }
        }
        
        if (packageInfo) {
          dependencies.push(packageInfo);
        }
      } catch (e) {
        // 忽略解析错误，继续处理下一行
        console.error(`解析行时出错: ${e.message}`);
      }
    }
  });

  // 将结果写入输出文件
  fs.writeFile(outputFilePath, dependencies.join('\n'), 'utf8', (writeErr) => {
    if (writeErr) {
      console.error(`写入输出文件出错: ${writeErr.message}`);
      process.exit(1);
    }
    
    console.log(`成功提取了 ${dependencies.length} 个依赖项`);
    console.log(`结果已保存到: ${outputFilePath}`);
  });
}); 