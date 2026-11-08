# A throw-away window for test_screen.py (ours, not the owner's): a label, a text box, a password box and two buttons. Writes what happened to the files named in $args.
param($stateFile, $titleFile)
Add-Type -AssemblyName System.Windows.Forms
$f = New-Object Windows.Forms.Form; $f.Text = "Test Window Alpha"; $f.Width = 420; $f.Height = 300; $f.StartPosition = "Manual"; $f.Left = 300; $f.Top = 200; $f.TopMost = $true
$l = New-Object Windows.Forms.Label; $l.Text = "Price 499 rupees today"; $l.Width = 300; $l.Top = 10; $f.Controls.Add($l)
$t = New-Object Windows.Forms.TextBox; $t.Name = "Message box"; $t.Width = 300; $t.Top = 40; $f.Controls.Add($t)
$p = New-Object Windows.Forms.TextBox; $p.Name = "Secret"; $p.Width = 300; $p.Top = 70; $p.UseSystemPasswordChar = $true; $f.Controls.Add($p)
$b1 = New-Object Windows.Forms.Button; $b1.Text = "Save"; $b1.Top = 110; $b1.Add_Click({ "saved" | Out-File -Append $stateFile }); $f.Controls.Add($b1)
$b2 = New-Object Windows.Forms.Button; $b2.Text = "Send message"; $b2.Top = 150; $b2.Width = 120; $b2.Add_Click({ "sent" | Out-File -Append $stateFile }); $f.Controls.Add($b2)
$tm = New-Object Windows.Forms.Timer; $tm.Interval = 200
$tm.Add_Tick({ if (Test-Path $titleFile) { $n = (Get-Content $titleFile -Raw).Trim(); if ($n -eq "QUIT") { $f.Close() } elseif ($n -and $f.Text -ne $n) { $f.Text = $n } }
               "box=" + $t.Text + "|pw=" + $p.Text | Out-File "$stateFile.fields" })
$tm.Start()
$f.Add_Shown({ $f.Activate(); $t.Focus() })
[Windows.Forms.Application]::Run($f)
