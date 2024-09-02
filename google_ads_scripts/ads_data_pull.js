/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * This Google Ads script pulls the data for a given Google Ads account
 * (or MCC) for a given date range
 * It pulls the following data:
 * - Account name
 * - Campaign name
 * - Ad Group name
 * - Ad ID
 * - Ad Type
 * - Ad Strength
 * - Ad Final URLs
 * - Keywords
 * - Headlines
 * - Descriptions
 */

const REPORTING_OPTIONS = {
    // Comment out the following line to default to the latest reporting
    // version.
    // apiVersion: 'v15'
};

const SPREADSHEETURL = 'insert spreadsheet URL here';
const DATE_BEGIN = 'YYYY-MM-DD';
const DATE_END = 'YYYY-MM-DD';

// Max number of headlines and descriptions to pull. These are the max values
// that can be set for a responsive search ad.
const MAX_NUM_HEADLINES = 15;
const MAX_NUM_DESCRIPTIONS = 4;

/**
 * Main function. It pulls the data for a given Google Ads account (or MCC)
 * for a given date range.
 */
function main() {
  Logger.log(
      'Starting scipt execution in the following timeframe: ' + DATE_BEGIN +
      ' - ' + DATE_END);
  const sheet = writeSpreadsheetHeader();

  try {
    if (isAccountMCC()) {
      // Iterate over subaccounts
      const accountIterator = AdsManagerApp.accounts().get();
      while (accountIterator.hasNext()) {
        const currentAccount = accountIterator.next();
        AdsManagerApp.select(currentAccount);
        getCleanData(currentAccount, sheet);
      }
    } else {
      const currentAccount = AdsApp.currentAccount();
      getCleanData(currentAccount, sheet);
    }
  } catch (error) {
    Logger.log('Unable to retrieve data from the account.');
    Logger.log(error);
  }
  Logger.log('Succesfully retrieved data');
}

/**
 * Checks if the current account is an MCC.
 * @return {boolean} True if the current account is an MCC, false otherwise.
 */
function isAccountMCC() {
  try {
    AdsManagerApp.accounts();
  } catch (error) {
    return false;
  }
  return true;
}

/**
 * Writes the spreadsheet header to the spreadsheet.
 * @return {!Sheet} The sheet object.
 */
function writeSpreadsheetHeader() {
  const ss = SpreadsheetApp.openByUrl(SPREADSHEETURL);
  const sheet = ss.getActiveSheet();
  sheet.clear();
  const titleRow = [
    'Account', 'Campaign Name', 'Ad Group name', 'Ad ID', 'Ad Type',
    'Ad Strength', 'Ad Final URLs', 'Keywords',
  ];
  for (let i = 1; i <= MAX_NUM_HEADLINES; i++) {
    titleRow.push('Headline ' + i);
  }
  for (let i = 1; i <= MAX_NUM_DESCRIPTIONS; i++) {
    titleRow.push('Description ' + i);
  }
  sheet.appendRow(titleRow);
  return sheet;
}

/**
 * Gets the data for a given Google Ads account (or MCC) for a given date range.
 * @param {string} account The account to get the data for.
 * @param {!Sheet} sheet The sheet to write the data to.
 */
function getCleanData(account, sheet) {
  Logger.log(
      'Processing account ' + account.getCustomerId() + ' - ' +
      account.getName());
  const query = 'SELECT ad_group_ad.ad.id, ' +
      'ad_group_ad.ad.responsive_search_ad.descriptions, ' +
      'ad_group_ad.ad.responsive_search_ad.headlines, ' +
      'campaign.name, ad_group.name, ' +
      'ad_group_ad.ad_strength,  ' +
      'ad_group_ad.ad.type, ' +
      'ad_group_ad.ad.final_urls ' +
      'FROM ad_group_ad ' +
      'WHERE ' +
      'ad_group_ad.status = \'ENABLED\' AND ' +
      'ad_group_ad.ad.type = \'RESPONSIVE_SEARCH_AD\' AND ' +
      'segments.date BETWEEN \'' + DATE_BEGIN + '\' AND \'' + DATE_END + '\'';
  const searchResults = AdsApp.search(query);

  for (const row of searchResults) {
    const campaignName = row.campaign.name;
    const adGroupName = row.adGroup.name;
    const adID = row.adGroupAd.ad.id;
    const keywords = getKeywords(adGroupName, campaignName);
    const headlines = row.adGroupAd.ad.responsiveSearchAd.headlines;
    const descriptions = row.adGroupAd.ad.responsiveSearchAd.descriptions;
    const adStrength = row.adGroupAd.adStrength;
    const adType = row.adGroupAd.ad.type;
    const adURLs = (row.adGroupAd.ad.finalUrls).join(',');
    const rowToAdd = [
      account.getName(), campaignName, adGroupName, adID, adType, adStrength,
      adURLs, keywords
    ];
    for (let i = 1; i <= MAX_NUM_HEADLINES; i++) {
      if (headlines.length >= i) {
        rowToAdd.push(headlines[i - 1].text);
      } else {
        rowToAdd.push('');
      }
    }
    for (let i = 1; i <= MAX_NUM_DESCRIPTIONS; i++) {
      if (descriptions.length >= i) {
        rowToAdd.push(descriptions[i - 1].text);
      } else {
        rowToAdd.push('');
      }
    }
    sheet.appendRow(rowToAdd);
  }
}

/**
 * Gets the keywords for a given ad group and campaign.
 * @param {string} adGroupName The ad group name.
 * @param {string} campaignName The campaign name.
 * @return {string} Comma separeted keywords.
 */
function getKeywords(adGroupName, campaignName) {
  const query = 'SELECT ad_group_criterion.keyword.text, ' +
      'ad_group.id ' +
      'FROM keyword_view ' +
      'WHERE ' +
      'campaign.name = \'' + escapeString(campaignName) + '\' AND ' +
      'ad_group.name = \'' + escapeString(adGroupName) + '\' AND ' +
      'segments.date BETWEEN \'' + DATE_BEGIN + '\' AND \'' + DATE_END + '\' ' +
      'AND ad_group_criterion.status != \'REMOVED\'';
  const searchResults = AdsApp.search(query);
  const setKeyword = new Set();
  for (const row of searchResults) {
    setKeyword.add(row.adGroupCriterion.keyword.text);
  }
  return Array.from(setKeyword).join(',');
}
/**
 * Escapes a string for use in a Google Ads query.
 * @param {string} str The string to escape.
 * @return {string} The escaped string.
 */
function escapeString(str) {
  return str.replace(/'/g, '\\\'');
}