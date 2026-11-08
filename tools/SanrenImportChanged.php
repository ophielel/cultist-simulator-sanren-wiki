<?php
require_once '/var/www/html/maintenance/Maintenance.php';
class SanrenImportChanged extends Maintenance {
    public function execute() {
        $manifest = json_decode(file_get_contents('/build/pages.json'), true);
        $services = MediaWiki\MediaWikiServices::getInstance();
        $lookup = $services->getRevisionLookup();
        $updater = $services->getWikiPageFactory();
        $user = MediaWiki\User\User::newFromName('WikiAdmin');
        $changed = 0;
        foreach ($manifest as $page) {
            $title = MediaWiki\Title\Title::newFromText($page['title']);
            if (!$title) { $this->error('Invalid title: '.$page['title']."\n"); continue; }
            $expected = rtrim(str_replace(["\r\n","\r"],"\n",file_get_contents('/build/pages/'.$page['file'])));
            $isCss = str_ends_with($page['title'], '.css');
            $expectedModel = $isCss ? 'css' : 'wikitext';
            $revision = $lookup->getRevisionByTitle($title);
            $content = $revision?->getContent('main');
            $actual = rtrim(str_replace(["\r\n","\r"],"\n",$content?->getText() ?? ''));
            if ($actual === $expected && $content && $content->getModel() === $expectedModel) continue;
            $wiki = $updater->newFromTitle($title);
            $edit = $wiki->newPageUpdater($user);
            $newContent = $isCss ? new CssContent($expected) : new WikitextContent($expected);
            $edit->setContent('main', $newContent);
            $edit->saveRevision(MediaWiki\CommentStore\CommentStoreComment::newUnsavedComment('同步生成数据；规范化页面标题'));
            if (!$edit->isUnchanged()) $changed++;
            $this->output(".");
        }
        $this->output("Updated $changed pages\n");
    }
}
$maintClass = SanrenImportChanged::class;
require_once RUN_MAINTENANCE_IF_MAIN;
