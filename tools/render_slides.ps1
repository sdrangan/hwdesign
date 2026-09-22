<#
.SYNOPSIS
Render slides of a .pptx to PNG through PowerPoint itself.

.DESCRIPTION
Used to check a deck after editing it: what PowerPoint draws is what the class
sees, including fonts and equations. LibreOffice substitutes fonts it does not
have, so its preview can show text overflowing (or fitting) when the real deck
does neither.

The deck is opened read-only and windowless, and PowerPoint is left running if
it already had presentations open, so this does not disturb an editing session.
A deck open in PowerPoint cannot be written by a build script; close it first.

.EXAMPLE
tools\render_slides.ps1 -Deck units\unit04_procif\procif.pptx -OutDir out

.EXAMPLE
tools\render_slides.ps1 -Deck deck.pptx -OutDir out -Slides 4,9,30
#>
param(
    [Parameter(Mandatory)] [string] $Deck,
    [Parameter(Mandatory)] [string] $OutDir,
    # Slide numbers in presentation order; all of them when omitted.
    [int[]] $Slides = @(),
    # Pixel width; height follows the deck's aspect ratio.
    [int] $Width = 1600
)

New-Item -ItemType Directory -Force $OutDir | Out-Null
$ppt = New-Object -ComObject PowerPoint.Application
$hadOpen = $ppt.Presentations.Count
# Open(FileName, ReadOnly, Untitled, WithWindow): -1 = msoTrue, 0 = msoFalse
$pres = $ppt.Presentations.Open((Resolve-Path $Deck).Path, -1, 0, 0)
try {
    $h = [int]($Width * $pres.PageSetup.SlideHeight / $pres.PageSetup.SlideWidth)
    if ($Slides.Count -eq 0) { $Slides = 1..$pres.Slides.Count }
    foreach ($i in $Slides) {
        $file = Join-Path (Resolve-Path $OutDir).Path ("slide-{0:D2}.png" -f $i)
        $pres.Slides.Item($i).Export($file, "PNG", $Width, $h)
        Write-Output $file
    }
} finally {
    $pres.Close()
    if ($hadOpen -eq 0) { $ppt.Quit() }
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null
}
