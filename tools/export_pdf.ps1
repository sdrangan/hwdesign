<#
.SYNOPSIS
Export a .pptx to PDF through PowerPoint itself.

.DESCRIPTION
The PDF beside each deck (units/<unit>/<deck>.pdf) is what students download,
so it should be re-exported whenever the deck changes.  PowerPoint draws it,
with the deck's own fonts, as render_slides.ps1 does for PNGs.

The deck is opened read-only and windowless, and PowerPoint is left running if
it already had presentations open.

.EXAMPLE
tools\export_pdf.ps1 -Deck units\unit09_sharedmem\sharedmem.pptx

.EXAMPLE
tools\export_pdf.ps1 -Deck deck.pptx -Pdf out\deck.pdf
#>
param(
    [Parameter(Mandatory)] [string] $Deck,
    # Defaults to the deck's path with a .pdf extension.
    [string] $Pdf = ""
)

$deckPath = (Resolve-Path $Deck).Path
if (-not $Pdf) { $Pdf = [System.IO.Path]::ChangeExtension($deckPath, ".pdf") }
$Pdf = [System.IO.Path]::GetFullPath($Pdf)

$ppt = New-Object -ComObject PowerPoint.Application
$hadOpen = $ppt.Presentations.Count
# Open(FileName, ReadOnly, Untitled, WithWindow): -1 = msoTrue, 0 = msoFalse
$pres = $ppt.Presentations.Open($deckPath, -1, 0, 0)
try {
    $pres.SaveAs($Pdf, 32)          # 32 = ppSaveAsPDF
    Write-Output $Pdf
} finally {
    $pres.Close()
    if ($hadOpen -eq 0) { $ppt.Quit() }
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null
}
