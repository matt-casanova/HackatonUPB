$u = "http://localhost:8000/api/v1"
$h = "application/json"

function sat-post($ruta, $cuerpo) {
  try {
    Invoke-RestMethod -Method Post "$u/$ruta" -ContentType $h -Body ($cuerpo | ConvertTo-Json) | Format-List
  } catch {
    "HTTP " + [int]$_.Exception.Response.StatusCode + "  " + $_.ErrorDetails.Message
  }
}
function sat-estado    { Invoke-RestMethod "$u/fires/overview" | Format-List }
function sat-puntos    { (Invoke-RestMethod "$u/fires/points").points | Format-Table id,type,risk_score,risk_level,source_mode -AutoSize }
function sat-historial($n = "CHI-01") {
  $r = Invoke-RestMethod "$u/fires/history?node_id=$n"
  $items = if ($r.history) { $r.history } else { $r }
  $items | Select-Object -Last 8 | Format-Table -AutoSize
}
function sat-alertas   { (Invoke-RestMethod "$u/alerts").alerts | Format-Table id,node_id,risk_score,status,confirmed_by,decided_at -AutoSize }
function sat-pendiente { (Invoke-RestMethod "$u/alerts?status=PENDING").alerts | Format-Table id,node_id,risk_score,status,created_at -AutoSize }
function sat-status    { Invoke-RestMethod "$u/system/status" | Select-Object mqtt_connected,mock_mode,db,firms,weather,telegram,stats | ConvertTo-Json -Depth 4 }
function sat-reset     { Invoke-RestMethod -Method Post "$u/demo/reset" | Out-Null; "reset ok (normal, sin foco, PENDING cerradas)" }
function sat-escenario($n) { sat-post "demo/scenario" @{ scenario = $n } }
function sat-foco($on = $true) { sat-post "demo/hotspot" @{ active = $on; node_id = "CHI-01" } }
function sat-confirmar($id) { sat-post "alerts/$id/confirm" @{ operator = "demo" } }
function sat-falsa($id)     { sat-post "alerts/$id/false-alarm" @{ operator = "demo" } }
function sat-ayuda {
  "sat-reset | sat-escenario normal/seco/incendio | sat-foco / sat-foco `$false"
  "sat-estado | sat-puntos | sat-historial | sat-alertas | sat-pendiente | sat-status"
  "sat-confirmar ID | sat-falsa ID"
}
"Comandos cargados. Escribe sat-ayuda"
