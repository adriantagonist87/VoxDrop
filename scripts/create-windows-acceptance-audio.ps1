param([Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop'
if(Test-Path -LiteralPath $Output){throw 'Use a new fixture directory'}
New-Item -ItemType Directory -Path $Output|Out-Null
$voice=New-Object -ComObject SAPI.SpVoice
$voices=$voice.GetVoices()
$tokens=@($voices|ForEach-Object {$_})
$cases=@(
 @{language='de';voice='407';parts=@('Wir besprechen heute den Projektplan und die nächsten Aufgaben. Die Unterlagen werden gemeinsam geprüft und die Ergebnisse schriftlich festgehalten.','Nach der Pause bestätigen wir den Termin am Freitag. Das fertige Protokoll bleibt neben der Aufnahme. Damit endet unsere Besprechung.');required=@('projektplan','freitag','protokoll')},
 @{language='en';voice='409';parts=@('Today we discuss the project plan and the next tasks. We review the documents together and record the results in writing.','After the break we confirm the Friday deadline. The final report must be saved beside the recording. This concludes our meeting.');required=@('project','friday','report')}
)
$manifest=@()
foreach($case in $cases){
 $matching=@($tokens|Where-Object {($_.GetAttribute('Language').Split(';')) -contains $case.voice})
 if(-not $matching.Count){throw "Missing installed SAPI voice for $($case.language)"}
 $voice.Voice=$matching[0];$voice.Rate=0
 for($index=0;$index -lt 2;$index++){
  $stream=New-Object -ComObject SAPI.SpFileStream
  $stream.Format.Type=22
  $stream.Open((Join-Path $Output "$($case.language)-$index.wav"),3,$false)
  $voice.AudioOutputStream=$stream
  [void]$voice.Speak($case.parts[$index]);$stream.Close()
 }
 $manifest+=@{language=$case.language;parts=$case.parts;required=$case.required;voice=$matching[0].GetDescription();pause_seconds=20}
}
$manifest|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $Output 'references.json') -Encoding utf8
