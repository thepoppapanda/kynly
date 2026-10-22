[CmdletBinding()]
param(
    [ValidateLength(1, 80)]
    [string]$Title = 'Kynly notification test',
    [ValidateLength(1, 500)]
    [string]$Message = 'Windows desktop notifications are ready for a visual check.'
)
$ErrorActionPreference = 'Stop'
try {
    # Reuse the installed Windows PowerShell shortcut identity for this first test.
    # Dedicated Kynly application registration and click actions are future work.
    $apps = @(Get-StartApps)
    $registered = $apps | Where-Object { $_.AppID -eq 'Microsoft.Windows.PowerShell' } | Select-Object -First 1
    if (!$registered) {
        # Use the native system-directory shortcut identity, not x86/ISE/VS/Anaconda.
        $registered = $apps | Where-Object {
            $_.AppID -ieq '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
        } | Select-Object -First 1
    }
    if (!$registered) {
        throw 'Windows PowerShell notification identity was not found. Report this error before continuing.'
    }
    $appId = $registered.AppID
    $null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
    $null = [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime]
    $null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId)
    if ($notifier.Setting.ToString() -ne 'Enabled') {
        throw ('Windows notification setting is ' + $notifier.Setting.ToString())
    }
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml('<toast><visual><binding template="ToastGeneric"><text></text><text></text></binding></visual></toast>')
    $texts = $xml.GetElementsByTagName('text')
    $null = $texts.Item(0).AppendChild($xml.CreateTextNode($Title))
    $null = $texts.Item(1).AppendChild($xml.CreateTextNode($Message))
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    $notifier.Show($toast)
    Start-Sleep -Seconds 2
    Write-Output 'Notification submitted to Windows. Confirm the banner or Notification Center visually.'
} catch {
    Write-Error $_
    exit 1
}
