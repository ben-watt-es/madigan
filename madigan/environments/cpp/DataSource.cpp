#include <stdexcept>
#include <iostream>
#include "DataSource.h"

namespace madigan{

  void Synth::initParams(std::vector<double> _freq, std::vector<double> _mu,
                         std::vector<double> _amp, std::vector<double> _phase,
                         double _dX)
  {
    this->freq=_freq;
    this->mu=_mu;
    this->amp=_amp;
    this->initPhase=_phase;
    this->x=_phase;
    this->dX=_dX;
    for (int i=0; i < freq.size(); i++){
      std::string assetName = "sine_" + std::to_string(i);
      this->assets.push_back(Asset(assetName));
    }
    this->nAssets = assets.size();
    currentData_.resize(nAssets);;
  }

  Synth::Synth(){
    double _dX{0.01};
    vector<double> freq{1., 0.3, 2., 0.5};
    vector<double> mu{2., 2.1, 2.2, 2.3};
    vector<double> amp{1., 1.2, 1.3, 1.};
    vector<double> phase{0., 1., 2., 1.};
    initParams(freq, mu, amp, phase, dX);
  }

  Synth::Synth(std::vector<double> _freq, std::vector<double> _mu,
               std::vector<double> _amp, std::vector<double> _phase,
               double _dX){
    if ((_freq.size() == _mu.size()) && (_mu.size() == _amp.size()) &&
        (_amp.size() == _phase.size())){
      initParams(_freq, _mu, _amp, _phase, _dX);
    }
    else{
      throw std::length_error("parameters passed to DataSource of type Synth"
                              " need to be vectors of same length");
    }
  }

  Synth::Synth(Config config){
    bool allParamsPresent{true};
    if (config.find("generator_params") == config.end()){
      throw ConfigError("config passed but doesn't contain generator params");
      allParamsPresent = false;
    }
    Config params = std::any_cast<Config>(config["generator_params"]);
    for (auto key: {"freq", "mu", "amp", "phase", "dX"}){
      if (params.find(key) == params.end()){
        allParamsPresent=false;
        throw ConfigError("generator parameters don't have all required constructor arguments");
      }
    }
    if (allParamsPresent){
      vector<double> freq = std::any_cast<vector<double>>(params["freq"]);
      vector<double> mu = std::any_cast<vector<double>>(params["mu"]);
      vector<double> amp = std::any_cast<vector<double>>(params["amp"]);
      vector<double> phase = std::any_cast<vector<double>>(params["phase"]);
      double dX = std::any_cast<double>(params["dX"]);
      initParams(freq, mu, amp, phase, dX);
    }
    else{
      vector<double> freq{1., 0.3, 2., 0.5};
      vector<double> mu{2., 2.1, 2.2, 2.3};
      vector<double> amp{1., 1.2, 1.3, 1.};
      vector<double> phase{0., 1., 2., 1.};
      double dX{0.01};
      initParams(freq, mu, amp, phase, dX);
    }
  }

  Synth::Synth(pybind11::dict py_config): Synth::Synth(makeConfigFromPyDict(py_config)){
    // Config config = makeConfigFromPyDict(py_config);

  }

  const PriceVector& Synth::getData() {
    for (int i=0; i < nAssets; i++){
      currentData_[i] = mu[i] + amp[i] * std::sin(PI2*x[i]*freq[i]);
      x[i] += dX;
    }
    return currentData_;
  }

  const pybind11::array_t<double> Synth::getData_np(){
    for (int i=0; i < nAssets; i++){
      currentData_[i] = mu[i] + amp[i] * std::sin(PI2*x[i]*freq[i]);
      x[i] += dX;
    }
    return pybind11::array_t<double>(
                               {currentData_.size()},
                               {sizeof(double)},
                               currentData_.data()
                               );
  }


}// namespace madigan
