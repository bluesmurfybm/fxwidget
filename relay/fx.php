<?php
/**
 * fxwidget 환율 중계 (회사 서버에 올려서 사용)
 * 사용: https://내도메인/경로/fx.php?codes=FX_USDKRW,FX_JPYKRW
 * 응답: {"FX_USDKRW":1366.8,"FX_JPYKRW":880.5,"source":"naver","time":"..."}
 * 서버에서 네이버 API를 대신 호출하고 60초 캐시.
 */
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');

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
    $ctx = stream_context_create(['http' => ['timeout' => 8, 'header' => "User-Agent: Mozilla/5.0\r\n"]]);
    $raw = @file_get_contents("https://api.stock.naver.com/marketindex/exchange/$c", false, $ctx);
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
