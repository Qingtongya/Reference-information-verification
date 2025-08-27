import re
import json
from typing import List, Dict


class CitationIdentifier:
    def __init__(self, use_proxy=False, proxy_url=None):
        # 定义常见政府文件和企业内部文件的引用模式
        self.citation_patterns = {
            "政府文件": [
                r"《([^》]+)》(?:〔\d+〕)?(?:第\d+条|第\d+款)",
                r"《([^》]+)》\s*(?:〔\d{4}〕\d+号)",
                r"(?:根据|依据|按照|遵照)《([^》]+)》",
                r"《([^》]+)》(?:的)?(?:规定|要求|明确)",
                r"(?:国务院|发改委|工信部|财政部|商务部|人社部|自然资源部|生态环境部|住建部|交通运输部|水利部|农业农村部|卫健委|人民银行|国资委|海关总署|税务总局|市场监管总局|银保监会|证监会|外汇局)(?:〔\d+〕)?\d+号",
            ],
            "企业内部文件": [
                r"《([^》]+)》(?:V\d+\.\d+|\d+版)",
                r"《([^》]+)》(?:管理制度|管理规定|管理办法|实施细则)",
                r"《([^》]+)》(?:的)?(?:规定|要求|明确|标准)",
                r"(?:公司|集团|部门)(?:〔\d+〕)?\d+号",
                r"(?:根据|依据|按照|遵照)公司《([^》]+)》",
            ]
        }
        self.use_proxy = use_proxy
        self.proxy_url = proxy_url


    def identify_citations(self, api_key: str, text: str, candidate_citations: List[Dict] = None) -> List[Dict]:
        """使用大模型识别文档中的引用内容（补充识别）"""
        import requests

        # 如果已经有候选引用，只让大模型验证和补充
        if candidate_citations and len(candidate_citations) > 0:
            prompt = f"""
            请验证以下文本中可能存在的对企业内部文件和政府文件的引用，并补充识别其他引用。

            文本内容片段：
            {text[:4000]}  # 限制文本长度以减少token消耗

            已通过正则表达式识别出的候选引用：
            {json.dumps(candidate_citations, ensure_ascii=False)}

            请验证这些引用是否正确，并补充识别其他可能的引用。
            对于每个引用，请提取以下信息：
            1. 引用类型（政府文件/企业内部文件）
            2. 文件名称
            3. 引用内容（被引用的具体文字）
            4. 可能的文号或版本信息（如果有）

            请以JSON格式返回结果，包含一个数组，每个元素是一个引用对象，包含type, title, content, identifier字段。
            """
        else:
            prompt = f"""
            请分析以下文本，识别出所有对企业内部文件和政府文件的引用。
            对于每个引用，请提取以下信息：
            1. 引用类型（政府文件/企业内部文件）
            2. 文件名称
            3. 引用内容（被引用的具体文字）
            4. 可能的文号或版本信息（如果有）

            文本内容：
            {text[:4000]}  # 限制文本长度以减少token消耗

            请以JSON格式返回结果，包含一个数组，每个元素是一个引用对象，包含type, title, content, identifier字段。
            """

        try:
            # 调用硅基流动API
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "deepseek-ai/DeepSeek-R1",
                "max_tokens": 1024,
                "temperature": 0.3,
                "top_p": 0.8,
                "n": 1,
                "messages": [
                    {
                        "content": prompt,
                        "role": "user"
                    }
                ],
                "stream": False
            }

            # 配置会话
            session = requests.Session()
            if self.use_proxy and self.proxy_url:
                session.proxies = {
                    "http": self.proxy_url,
                    "https": self.proxy_url,
                }
            else:
                session.trust_env = False  # 不信任环境变量中的代理设置

            response = session.post("https://api.siliconflow.cn/v1/chat/completions",
                                    json=payload, headers=headers, timeout=300)
            response.raise_for_status()
            result = response.json()
            response_text = result['choices'][0]['message']['content']

            # 从响应中提取JSON部分
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                citations = json.loads(json_match.group())
                # 标记为大模型识别
                for citation in citations:
                    citation["method"] = "llm"
                return citations
            else:
                # 如果模型没有返回标准JSON，尝试手动解析
                return self.parse_citations_from_text(response_text)
        except Exception as e:
            print(f"大模型识别引用时出错: {str(e)}")
            return []