/**
 * 自动化前端功能测试脚本
 * 在浏览器控制台中运行此脚本进行快速测试
 */

async function testFrontendFeatures() {
  console.log('='.repeat(60));
  console.log('🧪 前端自动化测试');
  console.log('='.repeat(60));

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  let testResults = {
    passed: 0,
    failed: 0,
    tests: []
  };

  function test(name, condition, details = '') {
    if (condition) {
      console.log(`✅ ${name}`);
      testResults.passed++;
      testResults.tests.push({ name, status: 'PASS', details });
    } else {
      console.log(`❌ ${name}`);
      testResults.failed++;
      testResults.tests.push({ name, status: 'FAIL', details });
    }
  }

  // 1. 测试 API 连接
  console.log('\n📡 测试 API 连接...');
  try {
    const response = await fetch(`${API_URL}/health`);
    const data = await response.json();
    test('API 健康检查', response.ok, JSON.stringify(data));
  } catch (error) {
    test('API 健康检查', false, error.message);
  }

  // 2. 测试任务创建
  console.log('\n📝 测试任务创建...');
  try {
    const response = await fetch(`${API_URL}/api/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: 'Automated Test Task',
        input_prompt: 'Test task for automated testing'
      })
    });
    const task = await response.json();
    test('任务创建', response.status === 201, `Task ID: ${task.id}`);
    
    // 3. 测试任务列表
    console.log('\n📋 测试任务列表...');
    const listResponse = await fetch(`${API_URL}/api/tasks`);
    const listData = await listResponse.json();
    test('获取任务列表', listResponse.ok, `Total: ${listData.total || listData.length || 0}`);
    
    // 4. 测试任务详情
    console.log('\n🔍 测试任务详情...');
    const detailResponse = await fetch(`${API_URL}/api/tasks/${task.id}`);
    const detailData = await detailResponse.json();
    test('获取任务详情', detailResponse.ok, `Status: ${detailData.status}`);
    
    // 5. 测试 WebSocket URL
    console.log('\n🔌 测试 WebSocket URL...');
    const wsUrl = API_URL.replace(/^http/, 'ws') + `/ws/tasks/${task.id}`;
    test('WebSocket URL 格式', wsUrl.startsWith('ws://') || wsUrl.startsWith('wss://'), wsUrl);
    
  } catch (error) {
    test('任务操作', false, error.message);
  }

  // 6. 测试 DOM 元素
  console.log('\n🎨 测试 UI 元素...');
  test('页面标题存在', document.querySelector('h1') !== null);
  test('任务表单存在', document.querySelector('form') !== null || document.querySelector('textarea') !== null);
  test('任务列表容器存在', document.querySelector('[class*="grid"]') !== null || document.querySelector('[class*="space-y"]') !== null);

  // 输出测试结果
  console.log('\n' + '='.repeat(60));
  console.log('📊 测试结果汇总');
  console.log('='.repeat(60));
  console.log(`✅ 通过: ${testResults.passed}`);
  console.log(`❌ 失败: ${testResults.failed}`);
  console.log(`📊 总计: ${testResults.passed + testResults.failed}`);
  console.log(`📈 通过率: ${((testResults.passed / (testResults.passed + testResults.failed)) * 100).toFixed(1)}%`);
  
  return testResults;
}

// 如果在浏览器环境中，自动运行测试
if (typeof window !== 'undefined') {
  testFrontendFeatures().then(results => {
    window.testResults = results;
    console.log('\n💡 测试结果已保存到 window.testResults');
  });
}

export { testFrontendFeatures };

