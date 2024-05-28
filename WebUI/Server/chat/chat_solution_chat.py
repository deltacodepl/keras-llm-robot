import json
import asyncio
from fastapi import Body
from langchain.chains import LLMChain
from fastapi.responses import StreamingResponse
from WebUI.Server.chat.utils import History
from langchain.prompts.chat import ChatPromptTemplate
from WebUI.configs import SAVE_CHAT_HISTORY, USE_RERANKER, GetRerankerModelPath
from langchain.chat_models import ChatOpenAI
from langchain.callbacks import AsyncIteratorCallbackHandler
from WebUI.Server.chat.StreamHandler import StreamSpeakHandler
from WebUI.configs.basicconfig import (GetProviderByName, GetSpeechModelInfo, GetPromptChatSolution, GetSpeechForChatSolution, GetSystemPromptForChatSolution)
from WebUI.Server.utils import wrap_done, get_ChatOpenAI, GetModelApiBaseAddress, detect_device
from WebUI.configs.webuiconfig import InnerJsonConfigWebUIParse
from WebUI.configs.basicconfig import (ModelType, ModelSize, ModelSubType, ToolsType, GetModelInfoByName, ExtractJsonStrings, use_new_search_engine, use_knowledge_base, use_new_function_calling, use_new_toolboxes_calling, CallingExternalTools)
from WebUI.Server.db.repository import add_chat_history_to_db, update_chat_history
from typing import AsyncIterable, Dict, List, Optional, Union, Any

def GetNewAnswerForChatSolution(answer: str, tool_name: str, tool_type: ToolsType) ->str:
    new_answer = answer
    if tool_type == ToolsType.ToolKnowledgeBase:
        new_answer = answer + "\n\n" + f'It is necessary to access knowledge base `{tool_name}` to get more information.'
    elif tool_type == ToolsType.ToolSearchEngine:
        new_answer = answer + "\n\n" + f'It is necessary to call search engine `{tool_name}` to get more information.'
    elif tool_type == ToolsType.ToolFunctionCalling:
        new_answer = answer + "\n\n" + f'It is necessary to call the function `{tool_name}` to get more information.'
    elif tool_type == ToolsType.ToolToolBoxes:
        new_answer = answer + "\n\n" + f'It is necessary to call the function `{tool_name}` to get more information.'
    else:
        new_answer = answer + "\n\n" + f'It is necessary to call unknown tool `{tool_name}` to get more information.'
    return new_answer

def GetUserAnswerFromChatSolution(tool_name: str, tool_type: ToolsType) ->str:
    user_answer = ""
    if tool_type == ToolsType.ToolKnowledgeBase:
        user_answer = f'The knowledge base `{tool_name}` was called.'
    elif tool_type == ToolsType.ToolSearchEngine:
        user_answer = f'The search engine `{tool_name}` was called.'
    elif tool_type == ToolsType.ToolFunctionCalling:
        user_answer = f'The function `{tool_name}` was called.'
    elif tool_type == ToolsType.ToolToolBoxes:
        user_answer = f'The function `{tool_name}` was called.'
    else:
        user_answer = f'The unknown tool `{tool_name}` was called.'
    return user_answer

async def GetChatPromptFromFromSearchEngine(json_lists: list = [], query: str = "", answer: str = "", history: list[History] = [], chat_solution: Any = None) ->Union[ChatPromptTemplate, Any, Any]:
    from WebUI.Server.chat.search_engine_chat import lookup_search_engine
    if not json_lists or not query or not history or not chat_solution:
        return None, "", []
    se_query = query
    try:
        for item in json_lists:
            item_json = json.loads(item)
            arguments = item_json.get("arguments", {})
            if arguments:
                first_key = next(iter(arguments))
                first_value = arguments[first_key]
                if isinstance(first_value, str):
                    se_query = first_value
                    break
    except Exception as _:
        pass
    search_engine_name = chat_solution["config"]["search_engine"]["name"]
    docs = await lookup_search_engine(se_query, search_engine_name)
    source_documents = [
        f"""from [{inum + 1}] [{doc.metadata["source"]}]({doc.metadata["source"]}) \n\n{doc.page_content}\n\n"""
        for inum, doc in enumerate(docs)
    ]
    context = "\n".join([doc.page_content for doc in docs])
    if not context:
        return None, "", []
    prompt_template = f"""The user's question has been searched on the internet. Here is all the content retrieved from the search engine:
    {context}\n
"""
    history.append(History(role="user", content=query))
    history.append(History(role="assistant", content=answer))
    history.append(History(role="user", content=prompt_template))
    chat_prompt = ChatPromptTemplate.from_messages(
        [i.to_msg_template() for i in history])
    return chat_prompt, search_engine_name, source_documents

async def GetChatPromptFromKnowledgeBase(json_lists: list = [], query: str = "", answer: str = "", history: list[History] = [], chat_solution: Any = None) ->Union[ChatPromptTemplate, Any, Any]:
    from urllib.parse import urlencode
    from fastapi.concurrency import run_in_threadpool
    from WebUI.Server.reranker.reranker import LangchainReranker
    from WebUI.Server.knowledge_base.kb_doc_api import search_docs
    from WebUI.Server.knowledge_base.kb_service.base import KBServiceFactory
    from WebUI.Server.knowledge_base.utils import VECTOR_SEARCH_TOP_K, SCORE_THRESHOLD
    if not json_lists or not query or not history or not chat_solution:
        return None, "", []
    kb_query = query
    try:
        for item in json_lists:
            item_json = json.loads(item)
            arguments = item_json.get("arguments", {})
            if arguments:
                first_key = next(iter(arguments))
                first_value = arguments[first_key]
                if isinstance(first_value, str):
                    kb_query = first_value
                    break
    except Exception as _:
        pass
    knowledge_base_name = chat_solution["config"]["knowledge_base"]["name"]
    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return None, "", []
    docs = await run_in_threadpool(search_docs,
            query=kb_query,
            knowledge_base_name=knowledge_base_name,
            top_k=VECTOR_SEARCH_TOP_K,
            score_threshold=SCORE_THRESHOLD)
    if USE_RERANKER:
            reranker_model_path = GetRerankerModelPath()
            print("-----------------model path------------------")
            print(reranker_model_path)
            reranker_model = LangchainReranker(top_n=VECTOR_SEARCH_TOP_K,
                                            device=detect_device(),
                                            max_length=1024,
                                            model_name_or_path=reranker_model_path
                                            )
            print(docs)
            docs = reranker_model.compress_documents(documents=docs,
                                                     query=kb_query)
            print("---------after rerank------------------")
            print(docs)
    source_documents = []
    for inum, doc in enumerate(docs):
        filename = doc.metadata.get("source")
        parameters = urlencode({"knowledge_base_name": knowledge_base_name, "file_name": filename})
        base_url = "/"
        url = f"{base_url}knowledge_base/download_doc?" + parameters
        text = f"""from [{inum + 1}] [{filename}]({url}) \n\n{doc.page_content}\n\n"""
        source_documents.append(text)
    context = "\n".join([doc.page_content for doc in docs])
    if not context:
        return None, "", []
    prompt_template = f"""The user's issue has been searched through the knowledge base. Here is all the content retrieved:
    {context}\n
"""
    history.append(History(role="user", content=query))
    history.append(History(role="assistant", content=answer))
    history.append(History(role="user", content=prompt_template))
    chat_prompt = ChatPromptTemplate.from_messages(
        [i.to_msg_template() for i in history])
    return chat_prompt, knowledge_base_name, source_documents

async def GetChatPromptFromFunctionCalling(json_lists: list = [], query: str = "", answer: str = "", history: list[History] = []) ->Union[ChatPromptTemplate, Any, Any]:
    from WebUI.Server.funcall.funcall import RunNormalFunctionCalling
    if not json_lists or not history:
        return None, "", []
    result_list = []
    func_name = []
    for item in json_lists:
        name, result = RunNormalFunctionCalling(item)
        if result:
            func_name.append(name)
            result_list.append(result)
    source_documents = []
    for result in enumerate(result_list):
        source_documents.append(f"function - {func_name[0]}()\n\n{result}")
    context = "\n".join(result_list)
    if not context:
        return None, "", []
    prompt_template = f"""The function ''{func_name[0]}'' has been executed, and the result is as follows:
    {context}\n
"""
    history.append(History(role="user", content=query))
    history.append(History(role="assistant", content=answer))
    history.append(History(role="user", content=prompt_template))
    chat_prompt = ChatPromptTemplate.from_messages(
        [i.to_msg_template() for i in history])
    await asyncio.sleep(0.1)
    return chat_prompt, func_name[0], source_documents

async def GetChatPromptFromToolBoxes(json_lists: list = [], query: str = "", answer: str = "", history: list[History] = []) ->Union[ChatPromptTemplate, Any, Any]:
    from WebUI.Server.funcall.google_toolboxes.credential import RunFunctionCallingInToolBoxes
    if not json_lists or not history:
        return None, "", []
    result_list = []
    func_name = []
    for item in json_lists:
        name, result = RunFunctionCallingInToolBoxes(item)
        if result:
            func_name.append(name)
            result_list.append(result)
    source_documents = []
    for result in enumerate(result_list):
        source_documents.append(f"function - {func_name[0]}()\n\n{result}")
    context = "\n".join(result_list)
    if not context:
        return None, "", []
    prompt_template = f"""The function '{func_name[0]}' has been executed, and the result is as follows:
    {context}\n
"""
    history.append(History(role="user", content=query))
    history.append(History(role="assistant", content=answer))
    history.append(History(role="user", content=prompt_template))
    chat_prompt = ChatPromptTemplate.from_messages(
        [i.to_msg_template() for i in history])
    await asyncio.sleep(0.1)
    return chat_prompt, func_name[0], source_documents

async def GetChatPromptFromExternalTools(answer: str, query: str, history: List[History], chat_solution: Any) ->Union[ChatPromptTemplate, Any, Any, Any]:
    if not answer:
        return None, "", [], ToolsType.Unknown
    json_lists = ExtractJsonStrings(answer)
    if not json_lists:
        return None, "", [], ToolsType.Unknown
    if use_new_search_engine(json_lists):
        chat_prompt, tool_name, docs = await GetChatPromptFromFromSearchEngine(json_lists, query, answer, history, chat_solution)
        return chat_prompt, tool_name, docs, ToolsType.ToolSearchEngine
    if use_knowledge_base(json_lists):
        chat_prompt, tool_name, docs = await GetChatPromptFromKnowledgeBase(json_lists, query, answer, history, chat_solution)
        return chat_prompt, tool_name, docs, ToolsType.ToolKnowledgeBase
    if use_new_function_calling(json_lists):
        chat_prompt, tool_name, docs = await GetChatPromptFromFunctionCalling(json_lists, query, answer, history)
        return chat_prompt, tool_name, docs, ToolsType.ToolFunctionCalling
    if use_new_toolboxes_calling(json_lists):
        chat_prompt, tool_name, docs = await GetChatPromptFromToolBoxes(json_lists, query, answer, history)
        return chat_prompt, tool_name, docs, ToolsType.ToolToolBoxes
    return None, "", [], ToolsType.Unknown

async def chat_solution_chat(
    query: str = Body(..., description="User input: ", examples=["chat"]),
    prompt_language: str = Body("", description="prompt language", examples=["en-US"]),
    imagesdata: List[str] = Body([], description="image data", examples=["image"]),
    audiosdata: List[str] = Body([], description="audio data", examples=["audio"]),
    videosdata: List[str] = Body([], description="video data", examples=["video"]),
    history: List[History] = Body([],
                                  description="History chat",
                                  examples=[[
                                      {"role": "user", "content": "Who are you?"},
                                      {"role": "assistant", "content": "I am AI."}]]
                                  ),
    stream: bool = Body(False, description="stream output"),
    chat_solution: dict = Body({}, description="Chat Solution"),
    temperature: float = Body(0.7, description="Temperature", ge=0.0, le=1.0),
    max_tokens: Optional[int] = Body(None, description="max tokens."),
    ) -> StreamingResponse:
    history = [History.from_data(h) for h in history]

    async def chat_solution_chat_iterator(query: str,
        prompt_language: str = "",
        imagesdata: List[str] = [],
        audiosdata: List[str] = [],
        videosdata: List[str] = [],
        history: List[History] = [],
        stream: bool = True,
        chat_solution: dict = {},
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        ) -> AsyncIterable[str]:
        configinst = InnerJsonConfigWebUIParse()
        webui_config = configinst.dump()
        print("prompt_language: ", prompt_language)

        # test
        # init_credential("google_credentials.json", FULL_SCOPES)
        # search_criteria = "from: 'confirmation@aircanada.ca' AND after:2023/09/01 AND before:2024/03/01"
        # email_messages = search_in_gmails(search_criteria)
        # print("email_messages: ", email_messages)

        if isinstance(max_tokens, int) and max_tokens <= 0:
            max_tokens = None
        model_name = chat_solution["config"]["llm_model"]
        modelinfo : Dict[str, any] = {"mtype": ModelType.Unknown, "msize": ModelSize.Unknown, "msubtype": ModelSubType.Unknown, "mname": str}
        modelinfo["mtype"], modelinfo["msize"], modelinfo["msubtype"] = GetModelInfoByName(webui_config, model_name)
        modelinfo["mname"] = model_name
        speak_handler = None
        speech = GetSpeechForChatSolution(chat_solution, prompt_language)
        if speech:
            config = GetSpeechModelInfo(webui_config, speech.get("model", ""))
            if len(config):
                modeltype = config["type"]
                speechkey = config.get("speech_key", "")
                if speechkey == "[Your Key]":
                    speechkey = ""
                speechregion = config.get("speech_region", "")
                if speechregion == "[Your Region]":
                    speechregion = ""
                provider = config.get("provider", "")
                spspeaker = speech.get("speaker", "")
                if modeltype == "local" or modeltype == "cloud":
                    speak_handler = StreamSpeakHandler(run_place=modeltype, provider=provider, synthesis=spspeaker, subscription=speechkey, region=speechregion)
        system_prompt = GetSystemPromptForChatSolution(chat_solution)
        if system_prompt:
            system_msg = {
                'role': "system",
                'content': system_prompt
            }
            history = [History.from_data(system_msg)] + history
        prompt_template = GetPromptChatSolution(chat_solution, "english-prompt")
        input_msg = History(role="user", content=prompt_template).to_msg_template(False)
        chat_prompt = ChatPromptTemplate.from_messages(
            [i.to_msg_template() for i in history] + [input_msg])
        
        btalk = True
        chat_history_id = add_chat_history_to_db(chat_type="llm_chat", query=query)
        answer = ""
        docs = []
        tooltype = ToolsType.Unknown
        while btalk:
            btalk = False
            async_callback = AsyncIteratorCallbackHandler()
            callbackslist = [async_callback]
            if modelinfo["mtype"] == ModelType.Local:
                provider = GetProviderByName(webui_config, model_name)
                model = get_ChatOpenAI(
                    provider=provider,
                    model_name=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    callbacks=callbackslist,
                    )
            else:
                api_base = GetModelApiBaseAddress(modelinfo)
                model = ChatOpenAI(
                    streaming=True,
                    verbose=False,
                    openai_api_key="EMPTY",
                    openai_api_base=api_base,
                    model_name=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    callbacks=callbackslist,
                )
            chain = LLMChain(prompt=chat_prompt, llm=model)

            task = asyncio.create_task(wrap_done(
                chain.acall({"prompt": query}),
                async_callback.done),
            )
            answer = ""
            if stream:
                async for token in async_callback.aiter():
                    print(" ", token)
                    answer += token
                    if not btalk:
                        btalk, new_answer = CallingExternalTools(answer)
                        if btalk:
                            new_chat_prompt, tool_name, docs, tooltype = await GetChatPromptFromExternalTools(answer=answer, query=query, history=history, chat_solution=chat_solution)
                            if not new_chat_prompt:
                                btalk = False
                            else:
                                new_answer = GetNewAnswerForChatSolution(new_answer, tool_name, tooltype)
                                yield json.dumps(
                                    {"clear": new_answer, "chat_history_id": chat_history_id},
                                    ensure_ascii=False)
                                user_answer = GetUserAnswerFromChatSolution(tool_name, tooltype)
                                yield json.dumps(
                                    {"user": user_answer, "tooltype": tooltype.value},
                                    ensure_ascii=False)

                                chat_prompt = new_chat_prompt
                                break
                    if speak_handler: 
                        speak_handler.on_llm_new_token(token)
                    yield json.dumps(
                        {"text": token, "chat_history_id": chat_history_id},
                        ensure_ascii=False)
                if speak_handler: 
                    speak_handler.on_llm_end(None)
                if not btalk and docs:
                    yield json.dumps({"tooltype": tooltype.value, "docs": docs}, ensure_ascii=False)
                    docs = []
                    tooltype = ToolsType.Unknown
            else:
                async for token in async_callback.aiter():
                    answer += token
                    if not btalk:
                        btalk, new_answer = CallingExternalTools(answer)
                        if btalk:
                            new_chat_prompt, docs = await GetChatPromptFromExternalTools(answer=answer, query=query, history=history, chat_solution=chat_solution)
                            if not new_chat_prompt:
                                btalk = False
                            else:
                                chat_prompt = new_chat_prompt
                                break
                if not btalk:
                    yield json.dumps(
                        {"text": answer, "chat_history_id": chat_history_id},
                        ensure_ascii=False)
                    if docs:
                        yield json.dumps({"docs": docs}, ensure_ascii=False)
                    docs = []
                    if speak_handler: 
                        speak_handler.on_llm_new_token(answer)
                        speak_handler.on_llm_end(None)
            await task
        print("chat_solution_chat_iterator exit!")
        if SAVE_CHAT_HISTORY and len(chat_history_id) > 0:
            update_chat_history(chat_history_id, response=answer)

    return StreamingResponse(chat_solution_chat_iterator(query=query,
            prompt_language=prompt_language,
            imagesdata=imagesdata,
            audiosdata=audiosdata,
            videosdata=videosdata,
            history=history,
            stream=stream,
            chat_solution=chat_solution,
            temperature=temperature,
            max_tokens=max_tokens),
            media_type="text/event-stream")