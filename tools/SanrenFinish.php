<?php
/** One-shot background maintenance for the initial generated import. */
require_once '/var/www/html/maintenance/Maintenance.php';
class SanrenFinish extends Maintenance {
    public function execute() {
        $this->output("Purging parser caches\n");
        MediaWiki\MediaWikiServices::getInstance()->getParserCache()->deleteAll();
        $dbw = $this->getPrimaryDB();
        $dbw->newUpdateQueryBuilder()->update('page')->set(['page_touched' => $dbw->timestamp()])->where('1=1')->caller(__METHOD__)->execute();
        $this->output("Refreshing links\n");
        $this->runChild('MediaWiki\\Maintenance\\RefreshLinks');
        $this->output("Rebuilding recent changes\n");
        $this->runChild('MediaWiki\\Maintenance\\RebuildRecentchanges');
        $this->output("Updating site statistics\n");
        $this->runChild('MediaWiki\\Maintenance\\InitSiteStats');
        $this->output("Finished\n");
    }
}
$maintClass = SanrenFinish::class;
require_once RUN_MAINTENANCE_IF_MAIN;
