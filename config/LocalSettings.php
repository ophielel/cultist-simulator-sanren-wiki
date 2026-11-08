<?php
# 三刃使徒 Wiki · local MediaWiki configuration.
if (file_exists(__DIR__ . '/GeneratedSettings.php')) {
    require_once __DIR__ . '/GeneratedSettings.php';
} else {
    http_response_code(503);
    exit('Wiki is not installed.');
}
$wgMetaNamespace = '项目';
$wgMetaNamespaceTalk = '项目讨论';
$wgLanguageCode = 'zh-cn';
$wgDefaultUserOptions['variant'] = 'zh-cn';
$wgDefaultSkin = 'vector-2022';
$wgServer = 'http://localhost:8090';
$wgScriptPath = '';
$wgArticlePath = '/index.php?title=$1';
$wgUsePathInfo = false;
$wgScriptExtension = '.php';
$wgResourceBasePath = '/resources';
$wgStylePath = '/skins';
$wgExtensionAssetsPath = '/extensions';
$wgLogos = ['1x' => '/sanren/logo.svg', 'icon' => '/sanren/logo.svg'];
$wgFavicon = '/sanren/logo.svg';
$wgLocaltimezone = 'Asia/Shanghai';
$wgEnableEmail = false;
$wgEnableUserEmail = false;
$wgGroupPermissions['*']['edit'] = false;
$wgGroupPermissions['*']['createpage'] = false;
$wgGroupPermissions['*']['createtalk'] = false;
$wgGroupPermissions['*']['upload'] = false;
$wgGroupPermissions['user']['edit'] = true;
$wgGroupPermissions['user']['createpage'] = true;
$wgGroupPermissions['user']['upload'] = true;
$wgGroupPermissions['user']['upload_by_url'] = false;
$wgEnableUploads = true;
$wgFileExtensions = ['png', 'gif', 'jpg', 'jpeg', 'webp', 'svg', 'mp3', 'ogg', 'pdf'];
$wgUploadDirectory = "$IP/images";
$wgUploadPath = '/images';
$wgUseImageMagick = true;
$wgImageMagickConvertCommand = '/usr/bin/convert';
$wgMaxImageArea = 5.0e7;
$wgResponsiveImages = true;
$wgImageLimits = [[320,240],[640,480],[960,720],[1280,960]];
$wgThumbnailLimits = [120,150,180,200,250,300,320,400,600,800,1024];
$wgMiserMode = false;

wfLoadSkin('Vector');
wfLoadSkin('Timeless');
wfLoadExtensions([
    'ParserFunctions', 'Scribunto', 'SyntaxHighlight_GeSHi', 'Cite',
    'CategoryTree', 'ImageMap', 'InputBox', 'MultimediaViewer', 'VisualEditor',
    'WikiEditor', 'CodeEditor', 'PageImages', 'TemplateData',
]);
$wgVisualEditorAvailableNamespaces = [NS_MAIN => true];
$wgVisualEditorEnableWikitext = true;
$wgPFEnableStringFunctions = true;
$wgUseSiteCss = true;
$wgAllowUserCss = true;
$wgUseSiteJs = false;
$wgAllowSiteCSSOnRestrictedPages = true;
$wgJobRunRate = 1;
$wgRunJobsAsync = false;

define('NS_RAW', 3000);
define('NS_RAW_TALK', 3001);
$wgExtraNamespaces[NS_RAW] = '原始数据';
$wgExtraNamespaces[NS_RAW_TALK] = '原始数据讨论';
$wgContentNamespaces[] = NS_RAW;
$wgNamespacesWithSubpages[NS_MAIN] = true;
$wgNamespacesWithSubpages[NS_RAW] = true;
$wgNamespaceProtection[NS_RAW] = ['editinterface'];
$wgNamespacesToBeSearchedDefault[NS_MAIN] = true;
$wgNamespacesToBeSearchedDefault[NS_RAW] = false;
$wgDisableTextSearch = false;

# APCu is bundled with the official image; Redis can be enabled when php-redis is added.
$wgMainCacheType = CACHE_ACCEL;
$wgParserCacheType = CACHE_DB;
$wgMessageCacheType = CACHE_ACCEL;
$wgSessionCacheType = CACHE_DB;
$wgSessionName = 'sanren_wiki_session';
$wgCacheDirectory = "$IP/cache";
$wgUseFileCache = false;
$wgEnableAPI = true;
$wgEnableWriteAPI = true;
$wgAllowRobots = false;
$wgNoFollowLinks = true;
$wgDefaultRobotPolicy = 'noindex,nofollow';

require_once "$IP/SanrenHooks.php";
