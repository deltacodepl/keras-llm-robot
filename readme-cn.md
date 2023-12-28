# Keras-llm-robot Web UI

🌍 [READ THIS IN ENGLISH](readme.md)

这个项目基础代码继承自 Langchain-Chatchat项目(https://github.com/chatchat-space/Langchain-Chatchat) 底层架构使用Langchain和Fastchat等开源框架实现。本项目完全开源，目标是可离线部署和测试Huggingface网站上的大部分开源模型，并且可以通过配置将多个模型组合起来，实现多模态，RAG，Agent等功能。

---

## 目录
* [项目介绍](readme-cn.md#项目介绍)
* [环境配置](readme-cn.md#环境配置)
* [功能介绍](readme-cn.md#功能介绍)
    * [语言模型的功能](readme-cn.md#语言模型的功能)
      * [1. 加载模型](readme-cn.md#1-加载语言模型)
      * [2. 模型量化](readme-cn.md#2-模型量化)
      * [3. 模型微调](readme-cn.md#3-模型微调)
      * [4. 提示词模版](readme-cn.md#4-提示词模版)
    * [辅助模型的功能](readme-cn.md#辅助模型的功能)
      * [1. 知识库检索](readme-cn.md#1-知识库检索)
      * [2. 代码解释器](readme-cn.md#2-代码解释器)
      * [3. 语音识别模型](readme-cn.md#3-语音识别模型)
      * [4. 图像识别模型](readme-cn.md#4-图像识别模型)
      * [5. 函数定义](readme-cn.md#5-函数定义)
* [快速启动](readme-cn.md#快速启动)


## 项目介绍
由三个主界面组成，语言模型的聊天界面，语言模型的配置界面，辅助模型的工具和代理界面。

聊天界面如下图，语言模型是主要模型，当它被加载之后就可以使用聊天模式。语言模型也是多模态的发动机，目前项目支持几十种语言模型：
![Image1](./img/WebUI.png)

配置界面如下图：
![Image1](./img/Configuration.png)

工具和代理界面如下图：
![Image1](./img/Tools_Agent.png)

## 环境配置


## 功能介绍


## 快速启动


## 参考

Langchain项目地址：(https://github.com/langchain-ai/langchain)

Fastchat项目地址：(https://github.com/lm-sys/FastChat)