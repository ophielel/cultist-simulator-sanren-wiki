<?php
/** Short local links and project-only adjustments. */
$wgHooks['SetupAfterCache'][] = static function () {
    global $wgLogo;
    $wgLogo = '/sanren/logo.svg';
};
$wgHooks['BeforePageDisplay'][] = static function ($out, $skin) {
    $out->addMeta('robots', 'noindex,nofollow');
};
$wgHooks['ParserAfterTidy'][] = static function ($parser, &$text) {
    # Generated pages deliberately keep source text and table-based infoboxes.
};

# Apply the same visual identity to MediaWiki's UI namespace stylesheet.
$wgHooks['ResourceLoaderRegisterModules'][] = static function ($resourceLoader) {
};
