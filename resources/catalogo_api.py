import requests
import json
import time
import urllib3
from typing import List, Dict, Any

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class CatalogoAPI:
    def __init__(self):
        self.base_url = "https://appdeconsulta.com/index.php/backend/index.php"
        self.loja_id = "49a204fcc142"
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-requested-with": "XMLHttpRequest",
            "origin": "https://appdeconsulta.com",
            "referer": f"https://appdeconsulta.com/pub/{self.loja_id}",
            "user-agent": "Mozilla/5.0"
        }
        self.verify_ssl = False
    
    def buscar_catalogo_completo(self):
        url = f"{self.base_url}?route=public/loja/{self.loja_id}"
        print(f"\n🔍 Buscando catálogo: {url}")
        
        try:
            response = requests.get(url, headers=self.headers, verify=False, timeout=60)
            print(f"📥 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if "data" in data and "products" in data["data"]:
                    produtos = data["data"]["products"]
                    print(f"✅ {len(produtos)} produtos encontrados")
                elif "products" in data:
                    produtos = data["products"]
                    print(f"✅ {len(produtos)} produtos encontrados")
                else:
                    print(f"⚠️ Estrutura: {list(data.keys())}")
                    produtos = []
                return data
            else:
                print(f"❌ Erro HTTP {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            print(f"❌ Erro: {e}")
            return {"success": False, "error": str(e)}
    
    def extrair_produtos(self, response_catalogo):
        produtos = []
        if "data" in response_catalogo and "products" in response_catalogo["data"]:
            produtos = response_catalogo["data"]["products"]
        elif "products" in response_catalogo:
            produtos = response_catalogo["products"]
        elif isinstance(response_catalogo, list):
            produtos = response_catalogo
        
        print(f"📦 {len(produtos)} produtos extraídos")
        return produtos
    
    def consultar_estoque(self, produtos):
        url = f"{self.base_url}?route=public/loja/{self.loja_id}/estoque"
        product_ids = [str(p["id"]) for p in produtos if "id" in p]
        
        payload = {
            "product_ids": product_ids,
            "products": produtos
        }
        
        print(f"\n📤 Enviando {len(product_ids)} produtos para consulta de estoque...")
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, verify=False, timeout=120)
            print(f"📥 Status: {response.status_code}")
            
            if response.status_code == 422:
                print(f"❌ Erro 422: {response.text[:300]}")
                return {"success": False, "error": "Erro 422"}
            
            return response.json()
        except Exception as e:
            print(f"❌ Erro: {e}")
            return {"success": False, "error": str(e)}
    
    def extrair_produtos_com_estoque(self, response_estoque):
        if not response_estoque.get("success", False):
            print("❌ API retornou success=false")
            return []
        
        data = response_estoque.get("data", {})
        produtos = data.get("products", [])
        
        print(f"\n📊 Resumo:")
        print(f"  Solicitados: {data.get('requested_count', 0)}")
        print(f"  Resolvidos: {data.get('resolved_count', 0)}")
        print(f"  Falhas: {data.get('failed_count', 0)}")
        
        return produtos
    
    def organizar_por_estoque(self, produtos):
        estoques = {}
        
        for produto in produtos:
            estoque_id = str(produto.get("estoque", "sem_estoque"))
            if estoque_id not in estoques:
                estoques[estoque_id] = []
            
            estoques[estoque_id].append({
                "id": str(produto.get("id", "")),
                "codigo": produto.get("codigo", ""),
                "descricao": produto.get("descricao", produto.get("nome", "")),
                "unidade": produto.get("unidade", "UN"),
                "estoque": produto.get("estoque", "")
            })
        
        return estoques
    
    def processar_catalogo_completo(self):
        print("=" * 60)
        print("🚀 PROCESSANDO CATÁLOGO COMPLETO")
        print("=" * 60)
        
        # 1. Buscar catálogo
        catalogo = self.buscar_catalogo_completo()
        
        # 2. Extrair produtos
        produtos = self.extrair_produtos(catalogo)
        
        if len(produtos) == 0:
            print("❌ Nenhum produto encontrado")
            return {"success": False, "error": "Catálogo vazio"}
        
        # 3. Consultar estoque
        response_estoque = self.consultar_estoque(produtos)
        
        if not response_estoque.get("success", False):
            print("❌ Falha na consulta de estoque")
            return response_estoque
        
        # 4. Organizar
        produtos_com_estoque = self.extrair_produtos_com_estoque(response_estoque)
        estoques_organizados = self.organizar_por_estoque(produtos_com_estoque)
        
        return {
            "success": True,
            "catalogo": catalogo,
            "response_estoque": response_estoque,
            "produtos_com_estoque": produtos_com_estoque,
            "estoques_organizados": estoques_organizados
        }