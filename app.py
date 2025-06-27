import requests
import json
from openai import OpenAI
from datetime import datetime
import re
import gradio as gr
import threading
import time

class FinancialDataAgent:
    def __init__(self):
        self.NOVITA_AI_API_KEY = "sk_YULlLVl4AFU7E2RfzoU5q2IUDRj-OEI61NURh5vmzJM"
        self.client = OpenAI(
            base_url="https://api.novita.ai/v3/openai",
            api_key=self.NOVITA_AI_API_KEY,
        )
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"
        self.api_url = "https://canlipiyasalar.haremaltin.com/tmp/doviz.json?dil_kodu=tr"
        
        # Cache için
        self.last_data = None
        self.last_update = None
        
        # Finansal terimlerin Türkçe karşılıkları
        self.financial_keywords = {
            'altın': ['ALTIN', 'ONS', 'KULCEALTIN', 'CEYREK_YENI', 'CEYREK_ESKI', 
                     'YARIM_YENI', 'YARIM_ESKI', 'TEK_YENI', 'TEK_ESKI', 'ATA_YENI', 
                     'ATA_ESKI', 'ATA5_YENI', 'ATA5_ESKI', 'GREMESE_YENI', 'GREMESE_ESKI',
                     'AYAR22', 'AYAR14'],
            'döviz': ['USDTRY', 'EURTRY', 'GBPTRY', 'AUDTRY', 'CHFTRY', 'JPYTRY', 
                     'CADTRY', 'DKKTRY', 'NOKTRY', 'SEKTRY', 'SARTRY'],
            'parite': ['EURUSD', 'GBPUSD', 'AUDUSD', 'USDCHF', 'USDJPY', 
                      'USDCAD', 'USDSAR'],
            'gümüş': ['GUMUSTRY', 'XAGUSD', 'GUMUSUSD'],
            'metal': ['PLATIN', 'XPTUSD', 'PALADYUM', 'XPDUSD'],
            'kg': ['USDKG', 'EURKG'],
            'ratio': ['XAUXAG']
        }
        
        # Kod açıklamaları
        self.code_descriptions = {
            'ALTIN': 'Gram Altın (TL)',
            'ONS': 'Ons Altın (USD)',
            'KULCEALTIN': 'Külçe Altın (TL)',
            'CEYREK_YENI': 'Çeyrek Altın Yeni (TL)',
            'CEYREK_ESKI': 'Çeyrek Altın Eski (TL)',
            'YARIM_YENI': 'Yarım Altın Yeni (TL)',
            'YARIM_ESKI': 'Yarım Altın Eski (TL)',
            'TEK_YENI': 'Tam Altın Yeni (TL)',
            'TEK_ESKI': 'Tam Altın Eski (TL)',
            'ATA_YENI': 'Ata Altın Yeni (TL)',
            'ATA_ESKI': 'Ata Altın Eski (TL)',
            'ATA5_YENI': '5li Ata Altın Yeni (TL)',
            'ATA5_ESKI': '5li Ata Altın Eski (TL)',
            'GREMESE_YENI': 'Gremse Altın Yeni (TL)',
            'GREMESE_ESKI': 'Gremse Altın Eski (TL)',
            'AYAR22': '22 Ayar Altın (TL)',
            'AYAR14': '14 Ayar Altın (TL)',
            'USDTRY': 'Dolar/TL',
            'EURTRY': 'Euro/TL',
            'GBPTRY': 'Sterlin/TL',
            'AUDTRY': 'Avustralya Doları/TL',
            'CHFTRY': 'İsviçre Frangı/TL',
            'JPYTRY': 'Japon Yeni/TL',
            'CADTRY': 'Kanada Doları/TL',
            'EURUSD': 'Euro/Dolar',
            'GBPUSD': 'Sterlin/Dolar',
            'AUDUSD': 'Avustralya Doları/Dolar',
            'USDCHF': 'Dolar/İsviçre Frangı',
            'USDJPY': 'Dolar/Japon Yeni',
            'USDCAD': 'Dolar/Kanada Doları',
            'GUMUSTRY': 'Gümüş/TL',
            'XAGUSD': 'Gümüş/USD',
            'PLATIN': 'Platin/TL',
            'XPTUSD': 'Platin/USD',
            'PALADYUM': 'Paladyum/TL',
            'XPDUSD': 'Paladyum/USD',
            'USDKG': 'Dolar Altın Kg',
            'EURKG': 'Euro Altın Kg'
        }

    def fetch_financial_data(self):
        """API'den finansal verileri çeker"""
        try:
            # Cache kontrol et (5 dakikada bir güncelle)
            now = datetime.now()
            if (self.last_data and self.last_update and 
                (now - self.last_update).seconds < 300):
                return self.last_data
                
            response = requests.get(self.api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Cache'e kaydet
            self.last_data = data
            self.last_update = now
            
            return data
        except requests.exceptions.RequestException as e:
            print(f"API'den veri çekme hatası: {e}")
            return self.last_data if self.last_data else None

    def is_financial_query(self, user_input):
        """Kullanıcı girdisinin finansal bir sorgu olup olmadığını kontrol eder"""
        user_input_lower = user_input.lower()
        
        # Finansal terimler - daha spesifik
        financial_terms = [
            'altın', 'dolar', 'euro', 'sterlin', 'gümüş', 'platin', 'paladyum',
            'döviz', 'kur', 'fiyat', 'değer', 'çeyrek', 'yarım', 'tam', 'ata',
            'külçe', 'ons', 'gram', 'tl', 'usd', 'eur', 'gbp', 'chf', 'jpy',
            'cad', 'aud', 'piyasa', 'borsa', 'yatırım', 'metal', 'değerli',
            'ne kadar', 'kaç tl', 'kaç dolar', 'fiyatı', 'kurunu', 'gold',
            'silver', 'platinum', 'palladium', 'dollar', 'pound'
        ]
        
        # Finansal soru kalıpları
        financial_patterns = [
            r'\b(dolar|euro|sterlin|altın|gümüş)\s+(ne\s+kadar|kaç\s+tl|fiyat)',
            r'\b(kaç\s+tl|ne\s+kadar)\b',
            r'\b(fiyat|kur|değer)\b',
            r'\b(usd|eur|gbp|try)\b'
        ]
        
        # Kelime kontrolü
        word_match = any(term in user_input_lower for term in financial_terms)
        
        # Pattern kontrolü
        pattern_match = any(re.search(pattern, user_input_lower) for pattern in financial_patterns)
        
        return word_match or pattern_match

    def find_relevant_data(self, user_input, financial_data):
        """Kullanıcı sorusuna göre ilgili verileri bulur"""
        if not financial_data or 'data' not in financial_data:
            return None
            
        user_input_lower = user_input.lower()
        relevant_data = {}
        
        # Önce spesifik anahtar kelimeler için özel kontroller
        if any(word in user_input_lower for word in ['dolar', 'usd', 'dollar']):
            if 'USDTRY' in financial_data['data']:
                relevant_data['USDTRY'] = financial_data['data']['USDTRY']
            return relevant_data if relevant_data else None
            
        if any(word in user_input_lower for word in ['euro', 'eur', 'avrupa']):
            if 'EURTRY' in financial_data['data']:
                relevant_data['EURTRY'] = financial_data['data']['EURTRY']
            return relevant_data if relevant_data else None
            
        if any(word in user_input_lower for word in ['sterlin', 'pound', 'gbp', 'ingiliz']):
            if 'GBPTRY' in financial_data['data']:
                relevant_data['GBPTRY'] = financial_data['data']['GBPTRY']
            return relevant_data if relevant_data else None
            
        if any(word in user_input_lower for word in ['gümüş', 'silver']):
            for code in ['GUMUSTRY', 'XAGUSD']:
                if code in financial_data['data']:
                    relevant_data[code] = financial_data['data'][code]
            return relevant_data if relevant_data else None
        
        # Altın için özel kontrol
        if any(word in user_input_lower for word in ['altın', 'gold']):
            altın_codes = ['ALTIN', 'ONS', 'KULCEALTIN']
            # Spesifik altın türü aranıyor mu?
            if any(word in user_input_lower for word in ['çeyrek', 'ceyrek']):
                altın_codes = ['CEYREK_YENI', 'CEYREK_ESKI']
            elif any(word in user_input_lower for word in ['yarım', 'yarim']):
                altın_codes = ['YARIM_YENI', 'YARIM_ESKI']
            elif any(word in user_input_lower for word in ['tam', 'tek']):
                altın_codes = ['TEK_YENI', 'TEK_ESKI']
            elif any(word in user_input_lower for word in ['ata']):
                altın_codes = ['ATA_YENI', 'ATA_ESKI', 'ATA5_YENI', 'ATA5_ESKI']
            elif any(word in user_input_lower for word in ['külçe', 'kulce']):
                altın_codes = ['KULCEALTIN']
            elif any(word in user_input_lower for word in ['ons']):
                altın_codes = ['ONS']
            elif any(word in user_input_lower for word in ['gram']):
                altın_codes = ['ALTIN']
                
            for code in altın_codes:
                if code in financial_data['data']:
                    relevant_data[code] = financial_data['data'][code]
            return relevant_data if relevant_data else None
        
        # Spesifik kodları ara
        for code, data in financial_data['data'].items():
            code_desc = self.code_descriptions.get(code, code).lower()
            
            # Kod adı veya açıklaması soruda geçiyorsa ekle
            if (code.lower() in user_input_lower or 
                any(keyword in user_input_lower for keyword in code_desc.split())):
                relevant_data[code] = data
                
        # Eğer spesifik veri bulunamadıysa, genel kategorilere bak
        if not relevant_data:
            for category, codes in self.financial_keywords.items():
                if category in user_input_lower:
                    for code in codes:
                        if code in financial_data['data']:
                            relevant_data[code] = financial_data['data'][code]
                    break  # İlk kategori bulunduğunda dur
                    
        return relevant_data if relevant_data else None

    def format_financial_data(self, data):
        """Finansal verileri LLM için formatlar"""
        if not data:
            return "Finansal veri bulunamadı."
            
        formatted_text = "Güncel Finansal Veriler:\n"
        formatted_text += "=" * 40 + "\n"
        
        for code, info in data.items():
            name = self.code_descriptions.get(code, code)
            formatted_text += f"\n{name} ({code}):\n"
            formatted_text += f"  • Alış: {info.get('alis', 'N/A')}\n"
            formatted_text += f"  • Satış: {info.get('satis', 'N/A')}\n"
            formatted_text += f"  • Kapanış: {info.get('kapanis', 'N/A')}\n"
            formatted_text += f"  • Günlük En Düşük: {info.get('dusuk', 'N/A')}\n"
            formatted_text += f"  • Günlük En Yüksek: {info.get('yuksek', 'N/A')}\n"
            formatted_text += f"  • Güncelleme: {info.get('tarih', 'N/A')}\n"
            
            # Yön bilgisi varsa ekle
            if info.get('dir'):
                direction_info = []
                if info['dir'].get('alis_dir'):
                    direction_info.append(f"Alış: {info['dir']['alis_dir']}")
                if info['dir'].get('satis_dir'):
                    direction_info.append(f"Satış: {info['dir']['satis_dir']}")
                if direction_info:
                    formatted_text += f"  • Yön: {', '.join(direction_info)}\n"
            formatted_text += "-" * 30 + "\n"
            
        return formatted_text

    def get_ai_response(self, user_input, financial_context=""):
        """AI'dan yanıt alır"""
        try:
            system_prompt = """Sen bir finansal danışman asistanısın. Altın, döviz ve değerli metal piyasaları hakkında uzman bilgiye sahipsin. 

Görevin:
1. Eğer kullanıcı finansal veriler (altın, döviz, gümüş vb.) hakkında soru soruyorsa, verilen güncel piyasa verilerini kullanarak detaylı ve açıklayıcı yanıt ver.
2. Finansal olmayan sorularda normal sohbet modunda yanıt ver.
3. Fiyatları belirtirken hangi para biriminde olduğunu açıkça belirt.
4. Yatırım tavsiyesi verme, sadece piyasa bilgisi paylaş.
5. Türkçe yanıt ver ve samimi bir ton kullan.
6. Yanıtlarını emojiler ile zenginleştir ama abartma.

Önemli: Sadece verilen güncel verileri kullan, tahmin yapma."""

            messages = [
                {"role": "system", "content": system_prompt},
            ]
            
            if financial_context:
                messages.append({
                    "role": "system", 
                    "content": f"Güncel piyasa verileri:\n{financial_context}"
                })
                
            messages.append({"role": "user", "content": user_input})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1000,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"❌ AI yanıt hatası: {e}"

    def get_market_summary(self):
        """Piyasa özeti döndürür"""
        financial_data = self.fetch_financial_data()
        if not financial_data or 'data' not in financial_data:
            return "📊 Piyasa verilerine şu anda ulaşılamıyor."
            
        try:
            summary = "📊 **Güncel Piyasa Özeti**\n\n"
            
            # Önemli kurlar
            important_codes = ['USDTRY', 'EURTRY', 'GBPTRY', 'ALTIN', 'ONS', 'GUMUSTRY']
            
            for code in important_codes:
                if code in financial_data['data']:
                    data = financial_data['data'][code]
                    name = self.code_descriptions.get(code, code)
                    
                    # Yön ikonu
                    trend = ""
                    if data.get('dir'):
                        if data['dir'].get('satis_dir') == 'up':
                            trend = " 📈"
                        elif data['dir'].get('satis_dir') == 'down':
                            trend = " 📉"
                    
                    summary += f"**{name}**: {data.get('satis', 'N/A')}{trend}\n"
            
            # Güncelleme zamanı
            if financial_data.get('meta', {}).get('tarih'):
                summary += f"• **{name}**: {data.get('satis', 'N/A')}{trend}\n"
                
            return summary
            
        except Exception as e:
            return f"📊 Piyasa özeti hazırlanırken hata: {e}"

    def process_query(self, user_input, history):
        """Ana işlem fonksiyonu - Gradio için uyarlanmış"""
        if not user_input.strip():
            return history + [("", "❓ Lütfen bir soru sorun.")], ""
        
        # Geçmişe kullanıcı sorusunu ekle
        history = history + [(user_input, "")]
        
        try:
            # Finansal sorgu kontrolü
            if self.is_financial_query(user_input):
                # Finansal verileri çek
                financial_data = self.fetch_financial_data()
                
                if financial_data:
                    # İlgili verileri bul
                    relevant_data = self.find_relevant_data(user_input, financial_data)
                    
                    if relevant_data:
                        # Verileri formatla
                        formatted_data = self.format_financial_data(relevant_data)
                        
                        # AI'dan yanıt al
                        response = self.get_ai_response(user_input, formatted_data)
                    else:
                        response = self.get_ai_response(
                            user_input, 
                            "Üzgünüm, sorunuzla ilgili spesifik veri bulunamadı. Genel piyasa durumu hakkında bilgi verebilirim."
                        )
                else:
                    response = "❌ Üzgünüm, şu anda piyasa verilerine erişemiyorum. Lütfen daha sonra tekrar deneyin."
            else:
                response = self.get_ai_response(user_input)
                
            # Geçmişi güncelle
            history[-1] = (user_input, response)
            
        except Exception as e:
            response = f"❌ Hata oluştu: {e}"
            history[-1] = (user_input, response)
        
        return history, ""

# Global agent instance
agent = FinancialDataAgent()

def create_interface():
    """Gradio arayüzünü oluşturur"""
    
    # CSS stili
    css = """
    .gradio-container {
        max-width: 1200px !important;
        margin: auto !important;
    }
    .chat-message {
        font-size: 16px !important;
    }
    .market-summary {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    """
    
    with gr.Blocks(
        css=css,
        title="💰 Finansal AI Agent",
        theme=gr.themes.Soft()
    ) as interface:
        
        # Başlık
        gr.HTML("""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-bottom: 20px;'>
            <h1 style='color: white; margin: 0; font-size: 2.5em;'>💰 Finansal AI Agent</h1>
            <p style='color: white; margin: 10px 0 0 0; font-size: 1.2em;'>Altın, Döviz ve Değerli Metal Fiyatları Hakkında Her Şey!</p>
        </div>
        """)
        
        with gr.Row():
            with gr.Column(scale=2):
                # Chat arayüzü
                chatbot = gr.Chatbot(
                    label="💬 Sohbet",
                    height=500,
                    show_label=True,
                    elem_classes=["chat-message"]
                )
                
                with gr.Row():
                    msg = gr.Textbox(
                        label="Sorunuz",
                        placeholder="Örnek: Altın fiyatı ne kadar? Dolar kaç TL?",
                        scale=4
                    )
                    send_btn = gr.Button("📤 Gönder", variant="primary", scale=1)
                
                # Örnek sorular
                with gr.Row():
                    gr.Examples(
                        examples=[
                            ["Altın fiyatı ne kadar?"],
                            ["Dolar kaç TL?"],
                            ["Euro kuru nedir?"],
                            ["Çeyrek altın ne kadar?"],
                            ["Gümüş fiyatları nasıl?"],
                            ["Sterlin ne durumda?"]
                        ],
                        inputs=msg,
                        label="💡 Örnek Sorular"
                    )
            
            with gr.Column(scale=1):
                # Piyasa özeti
                market_summary = gr.Markdown(
                    value=agent.get_market_summary(),
                    label="📊 Piyasa Özeti",
                    elem_classes=["market-summary"]
                )
                
                refresh_btn = gr.Button("🔄 Piyasa Özetini Yenile", variant="secondary")
                
                # Bilgilendirme
                gr.HTML("""
                <div style='linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 8px; margin-top: 20px;'>
                    <h4>ℹ️ Bilgilendirme</h4>
                    <ul style='margin: 0; padding-left: 20px;'>
                        <li>Veriler anlık olarak çekilir</li>
                        <li>5 dakikada bir otomatik güncellenir</li>
                        <li>Yatırım tavsiyesi verilmez</li>
                        <li>Sadece bilgilendirme amaçlıdır</li>
                    </ul>
                </div>
                """)
        
        # Event handlers
        def handle_message(message, history):
            return agent.process_query(message, history)
        
        def handle_refresh():
            return agent.get_market_summary()
        
        # Mesaj gönderme
        send_btn.click(
            handle_message,
            inputs=[msg, chatbot],
            outputs=[chatbot, msg]
        )
        
        msg.submit(
            handle_message,
            inputs=[msg, chatbot],
            outputs=[chatbot, msg]
        )
        
        # Piyasa özeti yenileme
        refresh_btn.click(
            handle_refresh,
            outputs=market_summary
        )
        
        # Otomatik piyasa özeti güncelleme (her 5 dakikada)
        def auto_refresh():
            while True:
                time.sleep(300)  # 5 dakika
                try:
                    # Bu kısım Gradio'da çalışmayabilir, manuel yenileme kullanın
                    pass
                except:
                    pass
        
        # Footer
        gr.HTML("""
        <div style='text-align: center; padding: 20px; color: #666; border-top: 1px solid #eee; margin-top: 30px;'>
            <p>🤖 Finansal AI Agent - Altın, Döviz ve Değerli Maden Piyasaları</p>
            <p style='font-size: 0.9em;'>Veri Kaynağı: <a href='https://canlipiyasalar.haremaltin.com' target='_blank'>Canlı Piyasalar</a></p>
        </div>
        """)
    
    return interface

if __name__ == "__main__":
    # Gradio arayüzünü başlat
    interface = create_interface()
    interface.launch(
        share=True,  # Paylaşılabilir link oluştur
        server_name="0.0.0.0",  # Tüm IP'lerden erişim
        server_port=7860,  # Port
        show_error=True,  # Hataları göster # 
        inbrowser=True  # Otomatik tarayıcıda aç
    )
