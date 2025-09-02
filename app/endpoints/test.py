import asyncio
import json
import base64
import time
import subprocess
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from typing import Dict, Any, List, Optional

router = APIRouter()

class TestRunner:
    """Kör tester och samlar resultat."""
    
    def __init__(self):
        self.test_results = {}
        self.audio_data = {}
    
    async def run_specific_test(self, test_type: str) -> Dict[str, Any]:
        """Kör ett specifikt test baserat på typ."""
        test_configs = {
            "unit": {
                "name": "Enhetstester",
                "path": "tests/test_receive_text.py",
                "description": "Testar individuella moduler"
            },
            "api-mock": {
                "name": "API Mock-tester",
                "path": "tests/test_text_to_audio.py tests/test_send_audio.py",
                "description": "Testar API med mock-data"
            },
            "full-mock": {
                "name": "Fullständig Pipeline Mock",
                "path": "tests/test_full_tts_pipeline.py",
                "description": "Testar hela kedjan med mock-data"
            },
            "elevenlabs": {
                "name": "ElevenLabs API Test",
                "path": "tests/test_real_elevenlabs.py",
                "description": "Testar mot riktig ElevenLabs API"
            },
            "pipeline": {
                "name": "Fullständig Pipeline Test",
                "path": "tests/test_full_chain.py",
                "description": "Testar hela kedjan från frontend till audio"
            }
        }
        
        if test_type not in test_configs:
            raise ValueError(f"Okänd test-typ: {test_type}")
        
        config = test_configs[test_type]
        
        try:
            print(f"🚀 Startar {config['name']}...")
            
            # Kör testet med pytest
            cmd = [sys.executable, "-m", "pytest", "-v", "-s"]
            if " " in config["path"]:
                # För tester som kör flera filer
                cmd.extend(config["path"].split())
            else:
                cmd.append(config["path"])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent
            )
            
            # Analysera resultat
            success = result.returncode == 0
            output = result.stdout
            error = result.stderr
            
            return {
                "test_type": test_type,
                "test_name": config["name"],
                "description": config["description"],
                "success": success,
                "output": output,
                "error": error,
                "return_code": result.returncode,
                "command": " ".join(cmd)
            }
            
        except Exception as e:
            return {
                "test_type": test_type,
                "test_name": config["name"],
                "description": config["description"],
                "success": False,
                "output": "",
                "error": str(e),
                "return_code": -1,
                "command": " ".join(cmd) if 'cmd' in locals() else "unknown"
            }
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Kör alla tester och returnerar sammanfattning."""
        test_types = ["unit", "api-mock", "full-mock", "elevenlabs", "pipeline"]
        
        start_time = time.time()
        results = {}
        
        for test_type in test_types:
            result = await self.run_specific_test(test_type)
            results[test_type] = result
        
        total_time = time.time() - start_time
        
        return {
            "status": "completed",
            "total_time": round(total_time, 3),
            "tests": results,
            "summary": {
                "total": len(test_types),
                "passed": sum(1 for r in results.values() if r["success"]),
                "failed": sum(1 for r in results.values() if not r["success"])
            }
        }

def get_test_info() -> Dict[str, Any]:
    """Returnerar information om tillgängliga tester."""
    return {
        "unit": {
            "name": "Enhetstester",
            "description": "Testar individuella moduler",
            "command": "make test-unit",
            "url": "/api/test?test_type=unit"
        },
        "api-mock": {
            "name": "API Mock-tester", 
            "description": "Testar API med mock-data",
            "command": "make test-api-mock",
            "url": "/api/test?test_type=api-mock"
        },
        "full-mock": {
            "name": "Fullständig Pipeline Mock",
            "description": "Testar hela kedjan med mock-data",
            "command": "make test-full-mock",
            "url": "/api/test?test_type=full-mock"
        },
        "elevenlabs": {
            "name": "ElevenLabs API Test",
            "description": "Testar mot riktig ElevenLabs API",
            "command": "make test-elevenlabs",
            "url": "/api/test?test_type=elevenlabs"
        },
        "pipeline": {
            "name": "Fullständig Pipeline Test", 
            "description": "Testar hela kedjan från frontend till audio",
            "command": "make test-pipeline",
            "url": "/api/test?test_type=pipeline"
        }
    }

@router.get("/test")
async def test_endpoint(
    test_type: Optional[str] = Query(None, description="Typ av test att köra"),
    info: Optional[bool] = Query(False, description="Visa bara information utan att köra tester"),
    text: Optional[str] = Query(None, description="Text att testa med")
) -> Dict[str, Any]:
    """Enhetlig endpoint för tester - visar info och kör tester.
    
    Tillgängliga tester:
    - unit: Enhetstester (testar individuella moduler)
    - api-mock: API Mock-tester (testar API med mock-data)
    - full-mock: Fullständig Pipeline Mock (testar hela kedjan med mock-data)
    - elevenlabs: ElevenLabs API Test (testar mot riktig ElevenLabs API)
    - pipeline: Fullständig Pipeline Test (testar hela kedjan från frontend till audio)
    """
    
    # Hämta test-information
    test_info = get_test_info()
    
    # Om inga parametrar skickas, visa tillgängliga tester
    if not test_type and not info:
        return {
            "status": "info",
            "message": "Använd /test?test_type=<typ> för att köra specifika tester",
            "available_tests": test_info,
            "examples": [
                "/test?test_type=elevenlabs - Kör ElevenLabs API test",
                "/test?test_type=pipeline - Kör fullständig pipeline test",
                "/test?test_type=elevenlabs&text=Hej världen - Kör med egen text",
                "/test - Kör alla tester",
                "/test?info=true - Visa bara denna information"
            ]
        }
    
    # Om info=True, visa bara information
    if info:
        return {
            "status": "info",
            "message": "Använd /test?test_type=<typ> för att köra specifika tester",
            "available_tests": test_info,
            "examples": [
                "/test?test_type=elevenlabs - Kör ElevenLabs API test",
                "/test?test_type=pipeline - Kör fullständig pipeline test",
                "/test?test_type=elevenlabs&text=Hej världen - Kör med egen text",
                "/test - Kör alla tester",
                "/test?info=true - Visa bara denna information"
            ]
        }
    
    try:
        runner = TestRunner()
        
        if test_type:
            # Kör specifikt test
            if test_type not in test_info:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Okänd test-typ: {test_type}. Tillgängliga: {', '.join(test_info.keys())}"
                )
            
            # Sätt TEXT-miljövariabel om text angavs
            if text:
                import os
                os.environ["TEXT"] = text
            
            result = await runner.run_specific_test(test_type)
            return {
                "status": "completed",
                "test": result,
                "message": f"Körde {result['test_name']} med text: '{text or 'standardtext'}'",
                "available_tests": test_info,  # Inkludera info för enkelhet
                "test_text": text or "standardtext"
            }
        else:
            # Kör alla tester
            # Sätt TEXT-miljövariabel om text angavs
            if text:
                import os
                os.environ["TEXT"] = text
            
            results = await runner.run_all_tests()
            results["available_tests"] = test_info  # Inkludera info för enkelhet
            results["test_text"] = text or "standardtext"
            return results
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test execution failed: {str(e)}")

@router.get("/")
async def test_home() -> HTMLResponse:
    """Enkel startsida för tester."""
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TTS Test Center</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                margin: 20px; 
                max-width: 1000px; 
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 { color: #333; text-align: center; margin-bottom: 30px; }
            .section { 
                margin: 30px 0; 
                padding: 20px; 
                border: 1px solid #ddd; 
                border-radius: 8px;
                background: #fafafa;
            }
            .section h2 { color: #007bff; margin-top: 0; }
            .test-button { 
                background: #28a745; 
                color: white; 
                padding: 15px 25px; 
                border: none; 
                border-radius: 6px; 
                font-size: 16px; 
                cursor: pointer;
                margin: 10px;
                display: inline-block;
            }
            .test-button:hover { background: #218838; }
            .test-button.secondary { background: #6c757d; }
            .test-button.secondary:hover { background: #5a6268; }
            .text-input { 
                width: 100%; 
                padding: 12px; 
                border: 2px solid #ddd; 
                border-radius: 6px; 
                font-size: 16px; 
                margin: 10px 0;
            }
            .text-input:focus { border-color: #007bff; outline: none; }
            .result { 
                margin: 20px 0; 
                padding: 15px; 
                border-radius: 6px; 
                white-space: pre-wrap;
                font-family: monospace;
                font-size: 14px;
            }
            .success { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
            .error { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
            .info { background: #d1ecf1; border: 1px solid #bee5eb; color: #0c5460; }
            .loading { background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; }
            .file-list {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 15px;
                margin: 10px 0;
            }
            .file-item {
                padding: 8px;
                border-bottom: 1px solid #dee2e6;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .file-item:last-child { border-bottom: none; }
            .play-button {
                background: #007bff;
                color: white;
                padding: 5px 10px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 12px;
            }
            .play-button:hover { background: #0056b3; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎯 TTS Test Center</h1>
            
            <!-- Test Section -->
            <div class="section">
                <h2>🧪 Kör Tester</h2>
                <p>Välj text och klicka på test du vill köra:</p>
                
                <input type="text" id="testText" class="text-input" 
                       placeholder="Skriv text här (t.ex. 'Hej världen!') eller lämna tomt för standardtext">
                
                <div style="margin: 20px 0;">
                    <button class="test-button" onclick="runTest('elevenlabs')">
                        🎵 ElevenLabs API Test
                    </button>
                    <button class="test-button" onclick="runTest('pipeline')">
                        🔄 Fullständig Pipeline Test
                    </button>
                    <button class="test-button secondary" onclick="runAllTests()">
                        🔄 Kör Alla Tester
                    </button>
                </div>
                
                <div id="testResult"></div>
            </div>
            
            <!-- Audio Files Section -->
            <div class="section">
                <h2>🎵 Audio Filer</h2>
                <p>Här kan du spela upp och ladda ner genererade audio-filer:</p>
                
                <button class="test-button" onclick="loadAudioFiles()">
                    📂 Ladda Audio Filer
                </button>
                
                <div id="audioFiles"></div>
            </div>
        </div>
        
        <script>
        async function runTest(testType) {
            const testText = document.getElementById('testText').value;
            const resultDiv = document.getElementById('testResult');
            
            resultDiv.innerHTML = '<div class="loading">⏳ Kör test...</div>';
            
            try {
                let url = `/api/test?test_type=${testType}`;
                if (testText) {
                    url += `&text=${encodeURIComponent(testText)}`;
                }
                
                const response = await fetch(url);
                const data = await response.json();
                
                if (data.status === 'completed') {
                    const success = data.test.success ? '✅ Lyckades' : '❌ Misslyckades';
                    resultDiv.innerHTML = `
                        <div class="success">
                            <h3>${success}</h3>
                            <p><strong>Test:</strong> ${data.test.test_name}</p>
                            <p><strong>Text:</strong> ${data.test_text}</p>
                            <p><strong>Output:</strong></p>
                            <pre>${data.test.output || 'Ingen output'}</pre>
                        </div>
                    `;
                } else {
                    resultDiv.innerHTML = `<div class="error">❌ Fel: ${JSON.stringify(data)}</div>`;
                }
            } catch (error) {
                resultDiv.innerHTML = `<div class="error">❌ Fel: ${error.message}</div>`;
            }
        }
        
        async function runAllTests() {
            const testText = document.getElementById('testText').value;
            const resultDiv = document.getElementById('testResult');
            
            resultDiv.innerHTML = '<div class="loading">⏳ Kör alla tester...</div>';
            
            try {
                let url = '/api/test';
                if (testText) {
                    url += `?text=${encodeURIComponent(testText)}`;
                }
                
                const response = await fetch(url);
                const data = await response.json();
                
                if (data.status === 'completed') {
                    let resultHtml = '<div class="success"><h3>✅ Alla tester klara!</h3>';
                    resultHtml += `<p><strong>Text:</strong> ${data.test_text}</p>`;
                    resultHtml += `<p><strong>Resultat:</strong> ${data.summary.passed}/${data.summary.total} lyckades</p>`;
                    
                    for (const [testKey, testResult] of Object.entries(data.tests)) {
                        const status = testResult.success ? '✅' : '❌';
                        resultHtml += `<p>${status} ${testResult.test_name}: ${testResult.success ? 'Lyckades' : 'Misslyckades'}</p>`;
                    }
                    
                    resultHtml += '</div>';
                    resultDiv.innerHTML = resultHtml;
                } else {
                    resultDiv.innerHTML = `<div class="error">❌ Fel: ${JSON.stringify(data)}</div>`;
                }
            } catch (error) {
                resultDiv.innerHTML = `<div class="error">❌ Fel: ${error.message}</div>`;
            }
        }
        
        async function loadAudioFiles() {
            const audioDiv = document.getElementById('audioFiles');
            audioDiv.innerHTML = '<div class="loading">⏳ Laddar filer...</div>';
            
            try {
                const response = await fetch('/api/audio-files');
                const data = await response.json();
                
                if (data.files.length === 0) {
                    audioDiv.innerHTML = '<div class="info">📂 Inga audio-filer hittades. Kör ett test först!</div>';
                    return;
                }
                
                let html = '<div class="file-list">';
                html += `<h4>📂 ${data.files.length} filer hittade:</h4>`;
                
                data.files.forEach(file => {
                    const fileSizeKB = (file.size / 1024).toFixed(1);
                    const modifiedTime = new Date(file.modified * 1000).toLocaleString('sv-SE');
                    
                    html += `
                        <div class="file-item">
                            <div>
                                <strong>📁 ${file.name}</strong><br>
                                <small>${fileSizeKB} KB • ${file.type.toUpperCase()} • ${modifiedTime}</small>
                            </div>
                            <div>
                                ${file.type === '.wav' ? 
                                    `<button class="play-button" onclick="playAudio('${file.name}')">▶️ Spela</button>` : 
                                    `<span style="color: #6c757d;">PCM (ladda ner)</span>`
                                }
                                <button class="play-button" onclick="downloadFile('${file.name}')">📥 Ladda ner</button>
                            </div>
                        </div>
                    `;
                });
                
                html += '</div>';
                audioDiv.innerHTML = html;
                
            } catch (error) {
                audioDiv.innerHTML = `<div class="error">❌ Fel: ${error.message}</div>`;
            }
        }
        
        function playAudio(filename) {
            const audio = new Audio(`/api/download-audio/${filename}`);
            audio.play();
        }
        
        function downloadFile(filename) {
            window.open(`/api/download-audio/${filename}`, '_blank');
        }
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)
