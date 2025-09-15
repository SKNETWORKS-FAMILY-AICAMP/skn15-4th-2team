document.addEventListener('DOMContentLoaded', function() {
    const sections = document.querySelectorAll('section');
    const navButtons = document.querySelectorAll('.nav-button');
    const searchButton = document.getElementById('search-button');
    const generateButton = document.getElementById('generate-button');
    const companyNameInput = document.getElementById('company-name');
    const jobTitleInput = document.getElementById('job-title');
    const mySpecInput = document.getElementById('my-spec');
    const questionSelectContainer = document.getElementById('question-select-container');
    const questionSelect = document.getElementById('question-select');
    const selectedQuestionP = document.getElementById('selected-question');
    const useExampleCheckbox = document.getElementById('use-example');
    const languageSelect = document.getElementById('language-select');
    const loadingIndicator = document.getElementById('loading-indicator');

    /**
     * @description 선택된 기능(공고 검색 또는 자기소개서 작성) 섹션만 보이게 하고, 메뉴 버튼의 활성화 상태를 변경합니다.
     * @param {string} id - 활성화할 섹션의 ID (예: 'job-search' 또는 'cover-letter-writer')
     */
    window.showSection = function(id) {
        sections.forEach(section => {
            if (section.id === id) {
                section.classList.add('active');
            } else {
                section.classList.remove('active');
            }
        });
        navButtons.forEach(button => {
            if (button.onclick.toString().includes(id)) {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
    }

    /**
     * @description 필수 입력 필드(회사명, 직무, 스펙)가 모두 채워지면 '생성 및 첨삭' 버튼을 활성화합니다.
     */
    function updateGenerateButtonState() {
        const company = companyNameInput.value.trim();
        const job = jobTitleInput.value.trim();
        const spec = mySpecInput.value.trim();
        generateButton.disabled = !(company && job && spec);
    }

	// 입력 필드에 값이 변경될 때마다 버튼 상태를 업데이트합니다.
    companyNameInput.addEventListener('input', updateGenerateButtonState);
    jobTitleInput.addEventListener('input', updateGenerateButtonState);
    mySpecInput.addEventListener('input', updateGenerateButtonState);

    // 페이지 로드 시 초기 버튼 상태를 설정합니다.
    updateGenerateButtonState();

    /**
     * @description '공고 검색' 버튼 클릭 시, API를 호출하여 채용 공고를 검색하고 결과를 화면에 표시합니다.
     */
    searchButton.addEventListener('click', async () => {
        const specText = document.getElementById('search-spec').value;
        const resultsDiv = document.getElementById('search-results');
        resultsDiv.innerHTML = '<p>🔍 검색 중입니다... 잠시만 기다려 주세요.</p>';

        try {
            const response = await fetch('/api/search_jobs/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ spec: specText })
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            resultsDiv.innerHTML = '';
            
            for (const role in data) {
                const roleHeader = document.createElement('h3');
                roleHeader.textContent = `▶ ${role}`;
                resultsDiv.appendChild(roleHeader);

                if (data[role].length === 0) {
                    const noResults = document.createElement('p');
                    noResults.textContent = '- (결과 없음)';
                    resultsDiv.appendChild(noResults);
                } else {
                    data[role].forEach(job => {
                        const jobItem = document.createElement('div');
                        jobItem.classList.add('job-result-item');
                        jobItem.innerHTML = `
                            <h4>${job.title || '(제목 없음)'}</h4>
                            <p>🔗 <a href="${job.url}" target="_blank">링크</a></p>
                        `;
                        resultsDiv.appendChild(jobItem);
                    });
                }
            }
        } catch (error) {
            resultsDiv.innerHTML = `<p style="color:red;">오류 발생: ${error.message}</p>`;
            console.error('Fetch error:', error);
        }
    });

    /**
     * @description '자기소개서 생성 및 첨삭' 버튼 클릭 시,
     * 필수 입력 필드를 확인하고, 로딩 상태를 표시한 후,
     * 백엔드 API를 두 번 호출하여 자기소개서 생성 및 첨삭 결과를 받아옵니다.
     * 첫 번째 API는 회사 정보와 자소서 문항을 가져오고, 두 번째 API는 최종 자소서를 생성합니다.
     */
    generateButton.addEventListener('click', async () => {
        const company = companyNameInput.value.trim();
        const job = jobTitleInput.value.trim();
        const spec = mySpecInput.value.trim();
        const language = document.getElementById('language-select').value;
        const charLimit = document.getElementById('char-limit').value;
        const useExample = document.getElementById('use-example').checked;
        const selectedQuestion = questionSelect.value;

        const generatedResumeSection = document.getElementById('generated-resume-section');
        const feedbackSection = document.getElementById('feedback-section');
        const generatedResumeTextarea = document.getElementById('generated-resume');
        const feedbackTextarea = document.getElementById('feedback-text');

        if (!company || !job || !spec) {
            alert("필수 입력 ")
            return;
        }
        
		// 요청 시작: 로딩 표시 및 기존 결과 숨기기
        loadingIndicator.classList.remove('hidden');
        generatedResumeSection.classList.add('hidden'); // 기존 결과 숨기기
        feedbackSection.classList.add('hidden'); // 기존 결과 숨기기
        generatedResumeTextarea.value = ''; // 텍스트 영역 비우기
        feedbackTextarea.value = ''; // 텍스트 영역 비우기

        try {
			// 1단계: 회사 정보 및 문항 API 호출
            const infoResponse = await fetch('/api/get_company_info/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ company, job, language, use_example: useExample })
            });

            if (!infoResponse.ok) {
                throw new Error('회사 정보 조회에 실패했습니다.');
            }

            const infoData = await infoResponse.json();

            const companyInfoDiv = document.getElementById('company-info');
			
			// 회사 인재상 및 정보 표시
            if (infoData.company_culture) {
                companyInfoDiv.innerHTML = `<div class="status-message info">${infoData.company_culture}</div>`;
            } else if (infoData.message) {
                companyInfoDiv.innerHTML = `<div class="status-message info">${infoData.message}</div>`;
            }

			// 자소서 문항 드롭다운 업데이트
            const questions = infoData.questions;
            const questionSelect = document.getElementById('question-select');
            const selectedQuestionP = document.getElementById('selected-question');

            questionSelect.innerHTML = ''; // 기존 옵션 제거
            questions.forEach((q, index) => {
                const option = document.createElement('option');
                option.value = q;
                option.textContent = `${index + 1}. ${q}`;
                questionSelect.appendChild(option);
            });
            
            const selectedQuestion = questionSelect.value;
			// 2단계: 자기소개서 생성 API 호출
            const response = await fetch('/api/generate_resume/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    company,
                    job,
                    spec,
                    language,
                    char_limit: charLimit,
                    use_example: useExample,
                    question: selectedQuestion
                })
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
			
			// 생성된 자기소개서 및 첨삭 피드백 표시
            generatedResumeTextarea.value = data.final_resume || '생성 실패';
            feedbackTextarea.value = data.reflection_content || '피드백 생성 실패';
            
            // 3. 요청 성공: 로딩 인디케이터를 숨기고 결과를 보이게 합니다.
            generatedResumeSection.classList.remove('hidden');
            feedbackSection.classList.remove('hidden');

        } catch (error) {
            generatedResumeTextarea.value = `오류 발생: ${error.message}`;
            feedbackTextarea.value = `오류 발생: ${error.message}`;
            generatedResumeSection.classList.remove('hidden');
            feedbackSection.classList.remove('hidden');
            console.error('Fetch error:', error);
        } finally {
            // 5. 요청이 성공하든 실패하든, 로딩 인디케이터를 숨깁니다.
            loadingIndicator.classList.add('hidden');
        }
    });
});