$python = "C:\Users\david\AppData\Local\Programs\Python\Python312\python.exe"
$script = "C:\Users\david\Documents\remote-job-engine\skill\scripts\poll_jobs.py"
$dir    = "C:\Users\david\Documents\remote-job-engine\skill"
$log    = "C:\Users\david\Documents\remote-job-engine\skill\state\poller.log"
$tmp    = "$log.tmp"
$err    = "$log.err"

$proc = Start-Process -FilePath $python -ArgumentList "`"$script`"" `
    -WorkingDirectory $dir `
    -RedirectStandardOutput $tmp `
    -RedirectStandardError $err `
    -NoNewWindow -Wait -PassThru

$ts = Get-Date -Format "yyyy-MM-dd HH:mm"
Add-Content -Path $log -Value "[$ts]"
if (Test-Path $tmp) { Get-Content $tmp | Add-Content -Path $log; Remove-Item $tmp }
if (Test-Path $err) { Get-Content $err | Add-Content -Path $log; Remove-Item $err }

exit $proc.ExitCode
