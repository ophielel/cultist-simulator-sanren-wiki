<?php
require_once '/var/www/html/maintenance/Maintenance.php';
class SanrenCleanup extends Maintenance {
    public function execute() {
        $dbw = $this->getPrimaryDB();
        $services = MediaWiki\MediaWikiServices::getInstance();
        $deleted = 0;
        $rows = $dbw->newSelectQueryBuilder()->select(['page_id','page_namespace','page_title'])
            ->from('page')->where(['page_namespace' => 0])->caller(__METHOD__)->fetchResultSet();
        foreach ($rows as $row) {
            $text = str_replace('_',' ', $row->page_title);
            if (str_contains($text, '<') || str_contains($text, '>') || str_contains($text, '_完成_')) {
                $page = $services->getWikiPageFactory()->newFromID($row->page_id);
                if ($page) {
                    $page->doDeleteArticleReal('删除早期导入时含原始 HTML 标记的无效标题',
                        MediaWiki\User\User::newSystemUser('Maintenance script'), true);
                    $deleted++;
                }
            }
        }
        $this->output("Deleted $deleted invalid early-import pages\n");
    }
}
$maintClass = SanrenCleanup::class;
require_once RUN_MAINTENANCE_IF_MAIN;
