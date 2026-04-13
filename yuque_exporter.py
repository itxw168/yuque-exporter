#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import requests
from urllib.parse import urljoin, urlparse, unquote
import time


class YuqueExporter:
    def __init__(self, output_dir="output"):
        self.output_dir = output_dir
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        })
        
        os.makedirs(self.output_dir, exist_ok=True)
    
    def sanitize_filename(self, filename):
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename.strip()
    
    def parse_book_toc(self, text_content):
        """从页面内容中解析知识库目录信息"""
        patterns = [
            r'decodeURIComponent\("([^"]+)"\)',
            r'window\.g_config\s*=\s*({.*?});',
            r'g_config\s*=\s*({.*?});',
            r'window\.config\s*=\s*({.*?});',
            r'config\s*=\s*({.*?});'
        ]

        data = None
        for i, pattern in enumerate(patterns, 1):
            try:
                matches = re.search(pattern, text_content, re.DOTALL)
                if matches:
                    if "decodeURIComponent" in pattern:
                        encoded_data = matches.group(1)
                        decoded_data = unquote(encoded_data)
                        data = json.loads(decoded_data)
                    else:
                        json_str = matches.group(1)
                        data = json.loads(json_str)

                    if data:
                        break
            except Exception as e:
                print(f"模式{i}解析失败: {str(e)}")
                continue

        if data:
            if "book" in data and "toc" in data["book"]:
                return data
            elif "toc" in data:
                return {"book": {"toc": data["toc"]}}
            elif "data" in data and "book" in data["data"]:
                if "toc" in data["data"]["book"]:
                    toc_data = data["data"]["book"]["toc"]
                    return {"book": {"toc": toc_data}}
        
        return None
    
    def get_public_kb_docs(self, kb_url):
        response = self.session.get(kb_url)
        response.raise_for_status()
        
        book_data = self.parse_book_toc(response.text)
        
        if not book_data or "book" not in book_data or "toc" not in book_data["book"]:
            with open('debug_page.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            raise ValueError("无法找到知识库数据，请检查URL是否正确或查看debug_page.html")
        
        toc_data = book_data["book"]["toc"]
        docs = []
        self._parse_toc(toc_data, docs, kb_url)
        
        if not docs:
            self._extract_docs_from_links(response.text, docs, kb_url)
        
        return docs
    
    def _extract_docs_from_links(self, html_content, docs, base_url):
        """从页面中直接提取文档链接"""
        patterns = [
            r'href="(/[^/]+/[^/]+/[^/"]+)"[^>]*>([^<]+)<',
            r'href="(/[^/]+/[^/"]+)"[^>]*>([^<]+)<'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content)
            for href, title in matches:
                doc_url = urljoin(base_url, href)
                if not any(doc['url'] == doc_url for doc in docs):
                    docs.append({
                        'title': title.strip(),
                        'url': doc_url,
                        'slug': href,
                        'level': 0
                    })
    
    def _parse_toc(self, toc_items, docs, base_url, level=0):
        for item in toc_items:
            print(f"处理目录项: {item.get('title', '无标题')}, type: {item.get('type', 'unknown')}")
            
            item_type = item.get('type', '')
            if item_type and item_type not in ['doc', 'Doc', 'DOC', '']:
                print(f"跳过非文档类型: {item_type}")
                if 'children' in item:
                    self._parse_toc(item['children'], docs, base_url, level + 1)
                continue
            
            doc_identifier = item.get('url', '')
            
            if not doc_identifier:
                doc_identifier = item.get('slug', '')
            
            if not doc_identifier:
                doc_identifier = item.get('uuid', '') or item.get('doc_uuid', '')
            
            if doc_identifier:
                if doc_identifier.startswith('/'):
                    doc_identifier = doc_identifier[1:]
                
                parsed_base = urlparse(base_url)
                base_path = parsed_base.path.strip('/')
                namespace = base_path
                
                if doc_identifier.startswith(namespace):
                    doc_url = f"https://www.yuque.com/{doc_identifier}"
                else:
                    doc_url = f"https://www.yuque.com/{namespace}/{doc_identifier}"
                
                print(f"构建文档URL: {doc_url}")
                
                docs.append({
                    'title': item.get('title', ''),
                    'url': doc_url,
                    'slug': doc_identifier,
                    'uuid': item.get('uuid', ''),
                    'level': level,
                    'namespace': namespace
                })
            
            if 'children' in item:
                self._parse_toc(item['children'], docs, base_url, level + 1)
    
    def get_doc_markdown(self, doc_url):
        """获取文档的Markdown内容 - 直接访问markdown端点"""
        print(f"正在获取文档内容: {doc_url}")
        
        query = "attachment=true&latexcode=false&anchor=false&linebreak=true"
        markdown_url = f"{doc_url}/markdown?{query}"
        
        print(f"访问Markdown导出URL: {markdown_url}")
        
        try:
            export_response = self.session.get(markdown_url, timeout=30)
            export_response.raise_for_status()
            
            markdown = export_response.text.strip()
            
            if markdown and len(markdown) > 10:
                if markdown.lstrip().startswith('<!DOCTYPE') or markdown.lstrip().startswith('<html'):
                    print(f"返回了HTML页面，可能需要登录或文档不公开")
                else:
                    print(f"成功获取Markdown，长度: {len(markdown)}")
                    
                    title = "无标题"
                    try:
                        doc_page_response = self.session.get(doc_url, timeout=30)
                        doc_page_response.raise_for_status()
                        
                        title_match = re.search(r'<title>([^<]+)</title>', doc_page_response.text)
                        if title_match:
                            title = title_match.group(1).split('·')[0].split('|')[0].strip()
                    except Exception as e:
                        print(f"获取标题失败: {e}")
                    
                    return {
                        'title': title,
                        'markdown': markdown
                    }
        except Exception as e:
            print(f"Markdown端点请求失败: {e}")
        
        print("尝试从文档页面的appData中获取内容...")
        
        try:
            response = self.session.get(doc_url, timeout=30)
            response.raise_for_status()
            
            app_data_pattern = r'window\.appData\s*=\s*JSON\.parse\(decodeURIComponent\(("[^"]+")\)\)'
            app_data_match = re.search(app_data_pattern, response.text, re.DOTALL)
            
            if app_data_match:
                try:
                    encoded_data = app_data_match.group(1).strip('"')
                    decoded_data = unquote(encoded_data)
                    data = json.loads(decoded_data)
                    
                    if "doc" in data:
                        doc = data["doc"]
                        title = doc.get('title', '无标题')
                        
                        body_fields = ['body', 'body_asl', 'content', 'markdown']
                        for field in body_fields:
                            if field in doc:
                                body_content = doc[field]
                                if isinstance(body_content, str) and len(body_content) > 10:
                                    print(f"从appData的{field}字段获取成功，长度: {len(body_content)}")
                                    return {
                                        'title': title,
                                        'markdown': body_content
                                    }
                except Exception as e:
                    print(f"解析appData失败: {e}")
        except Exception as e:
            print(f"获取文档页面失败: {e}")
        
        raise ValueError(f"无法获取文档内容，请确保文档是公开的: {doc_url}")
    
    def process_markdown_images(self, markdown):
        """处理Markdown中的图片，保持原始URL"""
        img_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
        
        def replace_img(match):
            alt = match.group(1)
            url = match.group(2)
            
            if url.startswith('//'):
                url = 'https:' + url
            
            return f'![{alt}]({url})'
        
        return img_pattern.sub(replace_img, markdown)
    
    def export_doc(self, doc_info):
        try:
            print(f"正在导出: {doc_info['title']}")
            
            doc_data = self.get_doc_markdown(doc_info['url'])
            markdown = doc_data.get('markdown', '')
            
            if markdown:
                markdown = self.process_markdown_images(markdown)
            
            feishu_markdown = "发布人昵称：语雀 | 发布时间：2024-01-01 00:00:00\n\n"
            
            content = markdown
            if content.startswith('# '):
                content = '\n'.join(content.split('\n')[1:])
            
            feishu_markdown += content
            
            safe_title = self.sanitize_filename(doc_info['title'])
            if not safe_title:
                safe_title = doc_info['slug']
            
            filename = f"{safe_title}.md"
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(feishu_markdown)
            
            print(f"导出成功: {filepath}")
            return True
        
        except Exception as e:
            print(f"导出失败 {doc_info['title']}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def export_knowledge_base(self, kb_url):
        print(f"开始导出知识库: {kb_url}")
        
        try:
            docs = self.get_public_kb_docs(kb_url)
            print(f"找到 {len(docs)} 个文档")
            
            success_count = 0
            for doc in docs:
                if self.export_doc(doc):
                    success_count += 1
                time.sleep(0.5)
            
            print(f"\n导出完成！成功: {success_count}/{len(docs)}")
            print(f"输出目录: {os.path.abspath(self.output_dir)}")
            
        except Exception as e:
            print(f"导出知识库失败: {e}")
            import traceback
            traceback.print_exc()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='语雀公开知识库导出工具 - 导出Markdown格式，支持飞书导入')
    parser.add_argument('url', help='语雀公开知识库URL')
    parser.add_argument('-o', '--output', default='output', help='输出目录 (默认: output)')
    
    args = parser.parse_args()
    
    exporter = YuqueExporter(output_dir=args.output)
    exporter.export_knowledge_base(args.url)


if __name__ == '__main__':
    main()
