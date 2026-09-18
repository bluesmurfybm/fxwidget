<?php
/**
 * fxwidget 환율 중계 (회사 서버에 올려서 사용)
 * 사용: https://내도메인/경로/fx.php?codes=FX_USDKRW,FX_JPYKRW
 * 응답: {"FX_USDKRW":1366.8,"FX_JPYKRW":880.5,"source":"naver","time":"..."}
 * 서버에서 네이버 API를 대신 호출하고 60초 캐시.
 */
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');

function fx_http_get($url) {
    // 호스팅에 따라 allow_url_fopen 이 꺼져 있어 curl 우선
    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 8, CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_USERAGENT => 'Mozilla/5.0', CURLOPT_SSL_VERIFYPEER => false]);
        $r = curl_exec($ch); curl_close($ch);
        if ($r !== false && $r !== '') return $r;
    }
    if (ini_get('allow_url_fopen')) {
        $ctx = stream_context_create(['http' => ['timeout' => 8, 'header' => "User-Agent: Mozilla/5.0\r\n"],
                                      'ssl' => ['verify_peer' => false, 'verify_peer_name' => false]]);
        return @file_get_contents($url, false, $ctx);
    }
    return false;
}

$codes = array_filter(array_map('trim', explode(',', $_GET['codes'] ?? 'FX_USDKRW,FX_JPYKRW')));
$codes = array_values(array_filter($codes, fn($c) => preg_match('/^FX_[A-Z]{6}$/', $c)));
if (!$codes) { http_response_code(400); echo '{"error":"codes"}'; exit; }

$cacheDir = sys_get_temp_dir() . '/fxwidget_cache';
@mkdir($cacheDir, 0777, true);
$out = ['source' => 'naver', 'time' => date('c')];

foreach ($codes as $c) {
    $cf = "$cacheDir/$c.json";
    if (is_file($cf) && time() - filemtime($cf) < 60) {
        $out[$c] = (float) file_get_contents($cf);
        continue;
    }
    $raw = fx_http_get("https://api.stock.naver.com/marketindex/exchange/$c");
    $j = $raw ? json_decode($raw, true) : null;
    $v = $j['exchangeInfo']['closePrice'] ?? null;
    if ($v !== null) {
        $out[$c] = (float) str_replace(',', '', $v);
        @file_put_contents($cf, $out[$c]);
    } elseif (is_file($cf)) {
        $out[$c] = (float) file_get_contents($cf);   // 네이버 실패 시 마지막 캐시
        $out['source'] = 'cache';
    }
}
echo json_encode($out, JSON_UNESCAPED_UNICODE);
