Add-Type -AssemblyName System.Drawing
[Windows.Security.Cryptography.CryptographicBuffer, Windows.Security.Cryptography, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.FileAccessMode, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null

$imgFile = 'S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\brave_current_view.png'
$file = [Windows.Storage.StorageFile]::GetFileFromPathAsync($imgFile).GetAwaiter().GetResult()
$stream = $file.OpenAsync([Windows.Storage.FileAccessMode]::Read).GetAwaiter().GetResult()
$decoder = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream).GetAwaiter().GetResult()
$bitmap = $decoder.GetSoftwareBitmapAsync().GetAwaiter().GetResult()
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
$result = $engine.RecognizeAsync($bitmap).GetAwaiter().GetResult()

foreach ($line in $result.Lines) {
    Write-Host ('Line: ' + $line.Text)
    foreach ($word in $line.Words) {
        if ($word.Text -match 'zip|Upload|Select|Project|Drag|computer') {
            Write-Host ('  Word: ' + $word.Text + ' at X=' + $word.BoundingRect.X + ' Y=' + $word.BoundingRect.Y + ' W=' + $word.BoundingRect.Width + ' H=' + $word.BoundingRect.Height)
        }
    }
}
