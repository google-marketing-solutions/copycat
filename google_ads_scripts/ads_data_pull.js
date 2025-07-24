/**
 * Copyright 2025 Google LLC
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

const SPREADSHEET_URL = '';  // insert spreadsheet URL
const DATE_BEGIN = '';  // date format: 'YYYY-MM-DD'
const DATE_END = '';  // date format: 'YYYY-MM-DD'

// Comma separated list of Account IDs to include in the report
// This is empty by default, meaning that all accounts will be included
// If you add one or more account IDs below, only those will be included!
// Use double quotes for each ID, as shown in the example below.
// Example:
// const ACCOUNT_IDS = ['111-222-3333','444-555-6666'];
const ACCOUNT_IDS = [];

// Comma separated list of Campaign IDs to include in the report
// This is empty by default, meaning that all campaigns will be included
// If you add one or more campaign IDs below, only those will be included!
// No quotes are required in this case, as shown in the example below.
// Example:
// const CAMPAIGN_IDS = [12345678901,98765432109];
const CAMPAIGN_IDS = [];

// Max number of headlines and descriptions to pull. These are the max values
// that can be set for a responsive search ad.
const MAX_NUM_HEADLINES = 15;
const MAX_NUM_DESCRIPTIONS = 4;

/**
 * Initializes a new sheet in the spreadsheet, or clears an existing one.
 * It adds the header row for the ad data.
 * @param {string} sheetName The name of the sheet to initialize.
 * @return {!GoogleAppsScript.Spreadsheet.Sheet} The initialized sheet.
 */
function initializeSheet(sheetName) {
  const ss = SpreadsheetApp.openByUrl(SPREADSHEET_URL);
  const sheet = ss.getSheetByName(sheetName) || ss.insertSheet(sheetName);
  sheet.clear();

  const titleRow = [
    'Account ID', 'Account', 'Campaign ID', 'Campaign Name', 'Ad Group ID',
    'Ad Group name', 'Ad ID', 'Ad Type', 'Ad Strength', 'Ad Final URLs',
    'Keywords',
  ];
  for (let i = 1; i <= MAX_NUM_HEADLINES; i++) {
    titleRow.push('Headline ' + i);
  }
  for (let i = 1; i <= MAX_NUM_DESCRIPTIONS; i++) {
    titleRow.push('Description ' + i);
  }

  sheet.getRange(1, 1, 1, titleRow.length).setValues([titleRow]);

  return sheet;
}

/**
 * Appends rows of data to the specified sheet.
 * @param {!Array<!Array<string|number>>} rows The rows to append.
 * @param {!GoogleAppsScript.Spreadsheet.Sheet} sheet The sheet to append the rows to.
 */
function appendRowsToSheet(rows, sheet) {
  if (!rows?.length) {
    Logger.info('No values to write');
    return;
  }

  if (!rows[0]?.length || rows.some(row => row.length !== rows[0].length)) {
    Logger.error('Inconsistent rows - cannot write to spreadsheet');
  }

  sheet.getRange(
    sheet.getLastRow() + 1,
    1,
    rows.length,
    rows[0].length
  ).setValues(rows);
}

/**
 * Main function. It pulls the data for a given Google Ads account (or MCC)
 * for a given date range.
 */
function main() {
  Logger.log(`Starting script execution in the following timeframe: ${DATE_BEGIN} - ${DATE_END}`);
  const sheet = initializeSheet(AdsApp.currentAccount().getCustomerId());

  try {
    if (isAccountMCC()) {
      // Iterate over subaccounts
      let accountIteratorBuilder = AdsManagerApp.accounts();
      if (ACCOUNT_IDS?.length > 0) {
        accountIteratorBuilder = accountIteratorBuilder.withIds(ACCOUNT_IDS);
      }
      const accountIterator = accountIteratorBuilder.get();
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
  Logger.log('Successfully retrieved data');
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
 * Gets the data for a given Google Ads account (or MCC) for a given date range.
 * @param {!AdsApp.Account|!AdsManagerApp.Account} account The account to get the data for.
 * @param {!GoogleAppsScript.Spreadsheet.Sheet} sheet The sheet to write the data to.
 */
function getCleanData(account, sheet) {
  const accountId = account.getCustomerId();
  const accountName = account.getName();
  Logger.log(`Processing account ${accountId} - ${accountName}`);

  const results = [];

  let query = `SELECT
      ad_group.id,
      ad_group_ad.ad.id,
      ad_group_ad.ad.responsive_search_ad.descriptions,
      ad_group_ad.ad.responsive_search_ad.headlines,
      campaign.id,
      campaign.name,
      ad_group.name,
      ad_group_ad.ad_strength,
      ad_group_ad.ad.type,
      ad_group_ad.ad.final_urls
    FROM ad_group_ad
    WHERE ad_group_ad.status = 'ENABLED'
      AND ad_group_ad.ad.type = 'RESPONSIVE_SEARCH_AD'
      AND segments.date BETWEEN '${DATE_BEGIN}' AND '${DATE_END}'`;

  // Add filter by campaign ID if the list has any values
  if (CAMPAIGN_IDS?.length > 0) {
    query += ` AND campaign.id IN (${CAMPAIGN_IDS.join(',')})`;
  }

  const searchResults = AdsApp.search(query);

  const BATCH_SIZE = 5000;
  while (searchResults.hasNext()) {
    const batch = [];
    while (searchResults.hasNext() && batch.length < BATCH_SIZE) {
      const currentRow = searchResults.next();
      batch.push(currentRow);
    }

    const batchCampaigns = new Set(batch.map(row => row.campaign.id));
    const batchAdGroups = new Set(batch.map(row => row.adGroup.id));

    const batchKeywords = getAllKeywords(Array.from(batchCampaigns), Array.from(batchAdGroups));

    for (const row of batch) {
      const campaignId = row.campaign.id;
      const campaignName = row.campaign.name;
      const adGroupId = row.adGroup.id;
      const adGroupName = row.adGroup.name;
      const adId = row.adGroupAd.ad.id;
      const keywords = Array.from(batchKeywords?.[campaignId]?.[adGroupId] || []);
      const headlines = row.adGroupAd.ad.responsiveSearchAd.headlines;
      const descriptions = row.adGroupAd.ad.responsiveSearchAd.descriptions;
      const adStrength = row.adGroupAd.adStrength;
      const adType = row.adGroupAd.ad.type;
      const adURLs = (row.adGroupAd.ad.finalUrls).join(',');
      const rowToAdd = [
        account.getCustomerId(),
        account.getName(),
        campaignId,
        campaignName,
        adGroupId,
        adGroupName,
        adId,
        adType,
        adStrength,
        adURLs,
        `'${keywords.join(',')}`  // Fix to support keyword lists where the first keyword begins with a + sign
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
      results.push(rowToAdd);
    }
  }

  appendRowsToSheet(results, sheet);
}

/**
 * Gets the keywords for a given list of ad groups and campaigns.
 * @param {!Array<number>} campaigns List of campaign IDs to be included.
 * @param {!Array<number>} adGroups List of ad group IDs to be included.
 * @return {object} The results, structured as follows:
 *     {
 *        campaign1: {

 * @return {object} The results, structured as follows:
 *     {
 *        campaign1: {
 *          adGroup1-1: (set of keywords for ad group 1-1)
 *          adGroup1-2: (set of keywords for ad group 1-2)
 *        },
 *        campaign2: {
 *          adGroup2-1: (set of keywords for ad group 2-1)
 *          adGroup2-2: (set of keywords for ad group 2-2)
 *        },
 *        ...
 */
function getAllKeywords(campaigns, adGroups) {
  const results = {};

  const query = `SELECT
      campaign.id,
      ad_group.id,
      ad_group_criterion.keyword.text
    FROM keyword_view
    WHERE campaign.id IN (${campaigns.join(',')})
      AND ad_group.id IN (${adGroups.join(',')})
      AND segments.date BETWEEN '${DATE_BEGIN}' AND '${DATE_END}'
      AND ad_group_criterion.status != 'REMOVED'`;

  const searchResults = AdsApp.search(query);

  for (const row of searchResults) {
    const campaignId = row.campaign.id;
    const adGroupId = row.adGroup.id
    const keyword = row.adGroupCriterion.keyword.text;

    if (!results[campaignId]) {
      results[campaignId] = {};
    }

    if (!results[campaignId][adGroupId]) {
      results[campaignId][adGroupId] = new Set();
    }

    results[campaignId][adGroupId].add(keyword);
  }

  return results;
}
