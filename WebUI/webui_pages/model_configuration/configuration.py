import streamlit as st
from WebUI.webui_pages.utils import *
from WebUI.configs import *
from streamlit_modal import Modal
import streamlit.components.v1 as components
from WebUI.webui_pages import *
from WebUI.configs.webuiconfig import *
import time

training_devices_list = ["auto","cpu","gpu","mps"]
loadbits_list = ["16 bits","8 bits","4 bits"]
quantization_list = ["16 bits", "8 bits", "6 bits", "5 bits", "4 bits"]

def configuration_page(api: ApiRequest, is_lite: bool = False):
    running_model = ""
    webui_config = api.get_webui_config()
    configinst = InnerJsonConfigWebUIParse(webui_config)
    localmodel = configinst.get("ModelConfig").get("LocalModel")
    onlinemodel = configinst.get("ModelConfig").get("OnlineModel")
    embeddingmodel = configinst.get("ModelConfig").get("EmbeddingModel")
    chatconfig = configinst.get("ChatConfiguration")
    quantconfig = configinst.get("QuantizationConfiguration")
    finetunning = configinst.get("Fine-Tunning")
    prompttemplates = configinst.get("PromptTemplates")

    models_list = list(api.get_running_models())
    if len(models_list):
        running_model = models_list[0]
    localmodel_lists = [f"{key}" for key in localmodel]
    onlinemodel_lists = []
    for _, value in onlinemodel.items():
        modellist = value.get("modellist", [])
        onlinemodel_lists.extend(modellist)
    onlinemodel_lists = list(filter(None, onlinemodel_lists))
    all_model_lists = localmodel_lists + onlinemodel_lists

    index = 0
    current_model = all_model_lists[0]
    blocalmodel = True
    if running_model != "":
        try:
            index = all_model_lists.index(running_model)
            all_model_lists[index] += " (running)"
            current_model = running_model
            if index >= len(localmodel_lists):
                blocalmodel = False
        except ValueError:
            index = 0

    col1, col2 = st.columns(2)
    disabled = False
    with col1:
        current_model = st.selectbox(
                "Please Select LLM Model",
                all_model_lists,
                index=index,
            )
        index = all_model_lists.index(current_model)
        if index >= len(localmodel_lists):
            blocalmodel = False
        #if new_model == "None":
        #    disabled = True
        le_button = st.button(
            "Load & Eject",
            use_container_width=True,
        )
        if le_button:
            if current_model != "None":
                if current_model.endswith("(running)"):
                    current_model = current_model[:-10].strip()
                if current_model == running_model:
                    with st.spinner(f"Release Model: {current_model}, Please do not perform any actions or refresh the page."):
                        r = api.eject_llm_model(current_model)
                        if msg := check_error_msg(r):
                            st.error(msg)
                        elif msg := check_success_msg(r):
                            st.success(msg)
                            current_model = "None"
                            running_model = ""
                else:
                    with st.spinner(f"Loading Model: {current_model}, Please do not perform any actions or refresh the page."):
                        r = api.change_llm_model(running_model, current_model)
                        if msg := check_error_msg(r):
                            st.error(msg)
                        elif msg := check_success_msg(r):
                            st.success(msg)
                            running_model = current_model
    with col2:
        if blocalmodel:
            if current_model.endswith("(running)"):
                current_model = current_model[:-10].strip()
            pathstr = localmodel[current_model].get("path")
        else:
            pathstr = ""
        st.text_input("Local Path", pathstr)
        save_path = st.button(
            "Save Path",
            use_container_width=True,
        )
        if save_path:
            with st.spinner(f"Saving path, Please do not perform any actions or refresh the page."):
                time.sleep(1)
                if current_model != "None":
                    st.success("Save path success!")
                else:
                    st.error("Save path failed!")
    st.divider()

    if blocalmodel:
        tabparams, tabquant, tabembedding, tabtunning, tabprompt = st.tabs(["Parameters", "Quantization", "Embedding Model", "Fine-Tunning", "Prompt Templates"])
        with tabparams:
            localmodel_config = localmodel[current_model]
            with st.form("Parameter"):
                col1, col2 = st.columns(2)
                with col1:
                    sdevice = localmodel_config.get("device").lower()
                    if sdevice in training_devices_list:
                        index = training_devices_list.index(sdevice)
                    else:
                        index = 0
                    predict_dev = st.selectbox(
                        "Please select Device",
                        training_devices_list,
                        index=index,
                        disabled=disabled
                    )
                    nthreads = localmodel_config.get("cputhreads")
                    st.number_input("CPU Thread", value = nthreads, min_value=1, max_value=32, disabled=disabled)
                    maxtokens = chatconfig.get("tokens_length")
                    min = maxtokens.get("min")
                    max = maxtokens.get("max")
                    cur = maxtokens.get("cur")
                    step = maxtokens.get("step")
                    st.slider("Max tokens", min, max, cur, step, disabled=disabled)
                    temperature = chatconfig.get("Temperature")
                    st.slider("Temperature", 0.0, 1.0, temperature, 0.05, disabled=disabled)
                    epsilon_cutoff = chatconfig.get("epsilon_cutoff")
                    st.slider("epsilon_cutoff", 0.0, 1.0, epsilon_cutoff, 0.1, disabled=disabled)
                    eta_cutoff = chatconfig.get("eta_cutoff")
                    st.slider("eta_cutoff", 0.0, 1.0, eta_cutoff, 0.1, disabled=disabled)
                    diversity_penalty = chatconfig.get("diversity_penalty")
                    st.slider("diversity_penalty", 0.0, 1.0, diversity_penalty, 0.1, disabled=disabled)
                    repetition_penalty = chatconfig.get("repetition_penalty")
                    min = repetition_penalty.get("min")
                    max = repetition_penalty.get("max")
                    cur = repetition_penalty.get("cur")
                    step = repetition_penalty.get("step")
                    st.slider("repetition_penalty", min, max, cur, step, disabled=disabled)
                    length_penalty = chatconfig.get("length_penalty")
                    min = length_penalty.get("min")
                    max = length_penalty.get("max")
                    cur = length_penalty.get("cur")
                    step = length_penalty.get("step")
                    st.slider("length_penalty", min, max, cur, step, disabled=disabled)
                    encoder_repetition_penalty = chatconfig.get("encoder_repetition_penalty")
                    min = encoder_repetition_penalty.get("min")
                    max = encoder_repetition_penalty.get("max")
                    cur = encoder_repetition_penalty.get("cur")
                    step = encoder_repetition_penalty.get("step")
                    st.slider("encoder_repetition_penalty", min, max, cur, step, disabled=disabled)
                with col2:
                    seed = chatconfig.get("seed")
                    min = seed.get("min")
                    max = seed.get("max")
                    cur = seed.get("cur")
                    st.number_input("Seed (-1 for random)", value = cur, min_value=min, max_value=max, disabled=disabled)
                    nloadbits = localmodel_config.get("loadbits")
                    index = 0 if nloadbits == 16 else (1 if nloadbits == 8 else (2 if nloadbits == 4 else 16))
                    predict_dev = st.selectbox(
                        "Load Bits",
                        loadbits_list,
                        index=index,
                        disabled=disabled
                    )
                    top_p = chatconfig.get("top_p")
                    st.slider("Top_p", 0.0, 1.0, top_p, 0.1, disabled=disabled)
                    top_k = chatconfig.get("top_k")
                    min = top_k.get("min")
                    max = top_k.get("max")
                    cur = top_k.get("cur")
                    step = top_k.get("step")
                    st.slider("Top_k", min, max, cur, step, disabled=disabled)
                    typical_p = chatconfig.get("typical_p")
                    st.slider("Typical_p", 0.0, 1.0, typical_p, 0.1, disabled=disabled)
                    top_a = chatconfig.get("top_a")
                    st.slider("Top_a", 0.0, 1.0, top_a, 0.1, disabled=disabled)
                    tfs = chatconfig.get("tfs")
                    st.slider("tfs", 0.0, 1.0, tfs, 0.1, disabled=disabled)
                    no_repeat_ngram_size = chatconfig.get("no_repeat_ngram_size")
                    st.slider("no_repeat_ngram_size", 0, 1, no_repeat_ngram_size, 1, disabled=disabled)
                    guidance_scale = chatconfig.get("guidance_scale")
                    min = top_k.get("min")
                    max = top_k.get("max")
                    cur = top_k.get("cur")
                    step = top_k.get("step")
                    st.slider("guidance_scale", min, max, cur, step, disabled=disabled)
                    st.text("")
                    st.text("")
                    st.text("")
                    do_samples = chatconfig.get("do_samples")
                    st.checkbox('do samples', value=do_samples, disabled=disabled)
                submit_create_kb = st.form_submit_button(
                    "Save Parameters",
                    use_container_width=True,
                    disabled=disabled
                )
        with tabquant:
            with st.form("Quantization"):
                methods_lists = ["AutoGPTQ", "ExllamaV2", "Llamacpp"]
                st.selectbox(
                    "Methods",
                    methods_lists,
                    index=0,
                    disabled=disabled
                )
                st.selectbox(
                    "Quantization Bits",
                    quantization_list,
                    index=0,
                    disabled=disabled
                )
                format_lists = ["GPTQ", "GGUF", "AWQ"]
                st.selectbox(
                    "Format",
                    format_lists,
                    index=0,
                    disabled=disabled
                )
                submit_quantization = st.form_submit_button(
                    "Launch",
                    use_container_width=True,
                    disabled=disabled
                )
                if submit_quantization:
                    st.success("The model quantization has been successful, and the quantized file path is model/llama-2-7b-hf-16bit.bin.")

        with tabembedding:
            embedding_lists = [f"{key}" for key in embeddingmodel]
            st.selectbox(
                "Please Select Embedding Model",
                embedding_lists,
                index=0
            )

        with tabtunning:
            st.selectbox(
                "Please select Device",
                training_devices_list,
                index=0,
                disabled=disabled
            )
        with tabprompt:
            pass
    
    else:
        tabparams, tabapiconfig, tabprompt = st.tabs(["Parameters", "API Config", "Prompt"])
        with tabparams:
            with st.form("Parameter"):
                col1, col2 = st.columns(2)
                with col1:
                    pass

                with col2:
                    pass
                submit_params = st.form_submit_button(
                    "Save Parameters",
                    use_container_width=True
                )

        with tabapiconfig:
            with st.form("ApiConfig"):
                st.text_input("API Key", "")
                st.text_input("API Proxy", "")

                submit_config = st.form_submit_button(
                    "Save API Config",
                    use_container_width=True
                )
        
        with tabprompt:
            pass

    st.session_state["current_page"] = "configuration_page"
