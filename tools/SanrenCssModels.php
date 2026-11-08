<?php
require_once '/var/www/html/maintenance/Maintenance.php';
class SanrenCssModels extends Maintenance {
    public function execute() {
        $services = MediaWiki\MediaWikiServices::getInstance();
        $user = MediaWiki\User\User::newFromName('WikiAdmin');
        foreach (['Common.css','Vector.css','Vector-2022.css','Timeless.css'] as $name) {
            $title = MediaWiki\Title\Title::newFromText('MediaWiki:' . $name);
            $page = $services->getWikiPageFactory()->newFromTitle($title);
            $updater = $page->newPageUpdater($user);
            $updater->setContent('main', new CssContent($page->getContent()->getText()));
            $updater->saveRevision(MediaWiki\CommentStore\CommentStoreComment::newUnsavedComment('将站点主题页面设置为 CSS 内容模型'));
            $this->output($name . ': ' . $page->getContentModel() . "\n");
        }
        MediaWiki\MediaWikiServices::getInstance()->getResourceLoader()->getMessageBlobStore()->clear();
    }
}
$maintClass = SanrenCssModels::class;
require_once RUN_MAINTENANCE_IF_MAIN;
