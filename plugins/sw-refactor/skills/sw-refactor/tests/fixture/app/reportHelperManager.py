class ReportHelperManagerFactory:
    def createReportHelperManager(self):
        return ReportHelperManager()


class ReportHelperManager:
    def buildReport(self, itemId):
        if itemId <= 0:
            return {"ok": False}
        return {"ok": True, "id": itemId}
