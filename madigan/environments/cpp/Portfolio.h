#ifndef PORTFOLIO_H_
#define PORTFOLIO_H_

#include <vector>
#include <string>
#include <unordered_map>
#include <iostream>

#include<Eigen/Core>

#include "Assets.h"
#include "DataTypes.h"
#include "DataSource.h"


namespace madigan{


  class Account; // forward declare for friend class declaration below

  using std::string;

  class Portfolio {
  public:
    /* Portfolio(){}; */
    Portfolio(Assets assets, double initCash);
    Portfolio(string id, Assets assets, double initCash);
    Portfolio(string id, Assets assets, double initCash, Ledger portfolio);
    Portfolio(string id, std::vector<string> assets, double initCash);
    Portfolio(string id, std::vector<string> assets, double initCash, Ledger portfolio);
    Portfolio(const Portfolio& other);
    Portfolio& operator=(const Portfolio& other);
    Portfolio(const Portfolio&& other)=delete;
    Portfolio& operator=(const Portfolio&& other)=delete;
    ~Portfolio()=default;

    void setDataSource(DataSourceTick* source);
    void setRequiredMargin(double reqMargin){ requiredMargin_=reqMargin;}
    void setMaintenanceMargin(double maintenanceMargin){
      maintenanceMargin_=maintenanceMargin;}

    string id() const { return id_;}
    Assets assets() const {return assets_;}
    std::unordered_map<string, unsigned int> assetIdx() const;
    unsigned int assetIdx(const string code) const;
    const DataSourceTick* dataSource() const{ return dataSource_;}
    const PriceVectorMap& currentPrices() const { return currentPrices_;}
    const Ledger&  meanEntryPrices() const { return meanEntryPrices_; }

    double requiredMargin() const{ return requiredMargin_; }
    double maintenanceMargin() const{ return maintenanceMargin_; }
    int nAssets() const { return assets_.size();}
    double initCash() const {return initCash_;}
    double cash() const { return cash_;}
    double balance() const;
    const Ledger& ledger() const {return ledger_;}
    Ledger ledgerFull() const;
    Ledger ledgerNormed() const;
    Ledger ledgerAbsNormed() const;
    Ledger ledgerNormedFull() const;
    Ledger ledgerAbsNormedFull() const;
    AmountVector positionValues() const;
    AmountVector positionValuesFull() const;
    double assetValue() const;
    double borrowedAssetValue() const;
    Ledger  meanEntryValue() const;
    double usedMargin() const;
    AmountVector usedMarginLedger() const;
    double availableMargin() const;
    double borrowedMargin() const;
    const Ledger& borrowedMarginLedger() const;
    double equity() const;
    double pnl() const;
    AmountVector pnlPositions() const;
    double borrowedEquity() const;
    double borrowedMarginRatio() const { (requiredMargin_<1.)? 1./(1.-requiredMargin_): 0. ;}

    RiskInfo checkRisk() const;
    RiskInfo checkRisk(double amount_to_purchase) const;
    RiskInfo checkRisk(int assetIdx, double units) const;
    RiskInfo checkRisk(string assetCode, double units) const;

    /* double borrowedCash() const; */
    double operator[](string code) {
      return ledger_(assetIdx_[code]);
    }
    double operator[](int assetIdx) {
      return ledger_(assetIdx);
    }

    void handleTransaction(string asset, double tranactionPrice,
                           double units, double transactionCost);
    void handleTransaction(int assetIdx, double tranactionPrice,
                           double units, double transactionCost);

    void close(int assetIdx, double transactionPrice, double transactionCost);
    void close(string assetCode, double transactionPrice, double transactionCost)
    { close(assetIdx_.at(assetCode), transactionPrice, transactionCost); }

    friend std::ostream& operator<<(std::ostream& os, const Portfolio& port);

    friend class Broker;
    friend class Account;

  private:
    void registerAssets(Assets assets);
    void registerAssets(Assets assets, std::vector<unsigned int> order);

  private:
    // DONT FORGET TO ADD VARIABLES TO COPY CONSTRUCTORS
    string id_="ledger_default";
    double initCash_=1'000'000;
    Assets assets_;
    bool assetsRegistered{false};
    double cash_=initCash_;
    Ledger ledger_;
    /* Ledger usedMargin_; */
    double usedMargin_{0.};
    Ledger meanEntryPrices_;
    Ledger borrowedMargin_;
    double requiredMargin_{1.}; // default = no levarage need 100% margin
    double maintenanceMargin_{.25}; // reasonable default
    double borrowedMarginRatio_{(requiredMargin_<1.)? 1./(1.-requiredMargin_): 0. }; // defaults to 0.

    std::unordered_map<string, unsigned int> assetIdx_;
    bool registeredDataSource{false};
    std::vector<double> defaultPrices_; // just to have some default prices (init to 0.) when datasource is na
    PriceVectorMap currentPrices_{nullptr, 0};
    DataSourceTick* dataSource_{nullptr};

  };


} /*namespace madigan*/

#endif /*  PORTFOLIO_H_ */
