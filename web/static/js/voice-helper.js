export function testVoicePlayback(callback) {
    try {
        const test = new SpeechSynthesisUtterance("語音測試");
        test.lang = 'zh-TW';
        test.onend = () => callback(true);
        test.onerror = () => callback(false);
        speechSynthesis.speak(test);
    } catch {
        callback(false);
    }
}

export function enableVoice() {
    const msg = new SpeechSynthesisUtterance("語音已啟用");
    msg.lang = 'zh-TW';
    speechSynthesis.speak(msg);
}
