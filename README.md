# ✨ 취업하Job – 당신의 AI 취업 도우미

> Django 기반의 AI 취업 지원 웹 서비스  
> 자기소개서 생성부터 채용 공고 탐색까지, 당신의 취업 여정을 함께합니다.

---

## 👥 팀 소개

<table>
  <tr>
    <td align="center" width="150">
      <a href="https://github.com/juyeonkwon">
        <img src="https://github.com/juyeonkwon.png" width="80" style="border-radius:50%;" alt="권주연 아바타"/><br/>
        <strong>권주연</strong><br/><sub>[팀장]</sub><br/><code>@juyeonkwon</code><br/>
      </a>
    </td>
    <td align="center" width="150">
      <a href="https://github.com/solchna">
        <img src="https://github.com/solchna.png" width="80" style="border-radius:50%;" alt="조솔찬 아바타"/><br/>
        <strong>조솔찬</strong><br/><code>@solchna</code><br/>
      </a>
    </td>
    <td align="center" width="150">
      <a href="https://github.com/asdg441">
        <img src="https://github.com/asdg441.png" width="80" style="border-radius:50%;" alt="노건우 아바타"/><br/>
        <strong>노건우</strong><br/><code>@asdg441</code><br/>
      </a>
    </td>
    <td align="center" width="150">
      <a href="https://github.com/dahyun11">
        <img src="https://github.com/dahyun11.png" width="80" style="border-radius:50%;" alt="하다현 아바타"/><br/>
        <strong>하다현</strong><br/><code>@dahyun11</code><br/>
      </a>
    </td>
    <td align="center" width="150">
      <a href="https://github.com/jeong-mincheol">
        <img src="https://github.com/jeong-mincheol.png" width="80" style="border-radius:50%;" alt="정민철 아바타"/><br/>
        <strong>정민철</strong><br/><code>@jeong-mincheol</code><br/>
      </a>
    </td>
    <td align="center" width="150">
      <a href="https://github.com/AQUAQUA5">
        <img src="https://github.com/AQUAQUA5.png" width="80" style="border-radius:50%;" alt="오원장 아바타"/><br/>
        <strong>오원장</strong><br/><code>@AQUAQUA5</code><br/>
      </a>
    </td>
  </tr>
</table>

---

## 🗓️ 프로젝트 기간

📅 **2025년 9월 15일(월) ~ 9월 16일(화)**

---

## 📕 프로젝트 개요

### ✅ 목적

- 취업 준비 시 반복적인 작업(공고 탐색, 자소서 작성 등)에 많은 시간이 소요됩니다.
- **취업하Job**은 지원자의 조건과 스펙을 바탕으로 적합한 공고를 추천하고,
  기업 인재상 기반의 **맞춤형 자기소개서**를 자동으로 작성 및 첨삭합니다.

---

## 🧠 주요 기능

| 기능 | 설명 |
|------|------|
| 🔍 **공고 추천** | 입력된 스펙을 바탕으로 적합한 **채용공고를 자동 수집 및 필터링** |
| ✍️ **자기소개서 생성** | 기업 인재상 + 유저 스펙 기반으로 **맞춤형 자소서 초안 자동 생성** |
| 🪄 **자기소개서 첨삭** | 작성된 자소서를 바탕으로 **톤, 분량, 적합성** 중심의 AI 피드백 제공 |

---

## 🖥️ 시스템 구조

```
[사용자 입력]
      ↓
[의도 분류] → 자소서 / 공고 구분
      ↓
┌────────────────────┬────────────────────────────┐
│ [자기소개서]       │         [공고 추천]        │
│ 회사/직무/스펙 추출 │   스펙 기반 직무 키워드 추출 │
│ 인재상 & 예시 로딩 │   확장 키워드로 공고 크롤링  │
│ 자소서 생성 & 첨삭  │        공고 리스트 출력     │
└────────────────────┴────────────────────────────┘
      ↓
[Django 웹 UI 출력]
```

---

## 🏗️ 시스템 아키텍처

### 🔍 공고 추천 시스템

- LLM 기반 입력 분석 → 키워드 매핑
- 직무 키워드 확장 → Playwright 크롤링
- Django 웹 페이지에 채용 리스트 출력

<p align="center">
  <img src="https://github.com/user-attachments/assets/4c782f7d-fc6d-4a71-9fd3-79137ec2daf7" width="900" alt="공고 아키텍처"/>
</p>

---

### ✍️ 자기소개서 생성 시스템

- 사용자 입력 → 회사명, 직무, 스펙 추출
- 기업 인재상 / 자소서 예시 DB 조회
- LangGraph로 자소서 생성 → 첨삭 루프 수행
- 최종 결과는 Django UI로 제공

<p align="center">
  <img src="https://github.com/user-attachments/assets/251a6e96-69c1-49d2-9477-4962488901a8" width="900" alt="자기소개서 아키텍처"/>
</p>

---

## ⚙️ 기술 스택

### 🌐 웹 프레임워크
<p>
  <img src="https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white" />
</p>

### 🧠 AI & LLM
<p>
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white" />
  <img src="https://img.shields.io/badge/LangChain-4B8BBE?style=for-the-badge" />
  <img src="https://img.shields.io/badge/LangGraph-6969ff?style=for-the-badge" />
</p>

### 📊 데이터 분석 / 추천
<p>
  <img src="https://img.shields.io/badge/pandas-150458?style=for-the-badge&logo=pandas&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLAlchemy-cdcdcd?style=for-the-badge" />
</p>

### 🌐 크롤링 & 비동기
<p>
  <img src="https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white" />
  <img src="https://img.shields.io/badge/asyncio-005571?style=for-the-badge" />
</p>

### ☁️ 배포 & 인프라
<p>
  <img src="https://img.shields.io/badge/AWS-232F3E?style=for-the-badge&logo=amazonaws&logoColor=white" />
</p>

---

## 🎯 기대 효과

| 항목 | 효과 |
|------|------|
| ⏱ **시간 절약** | 반복적인 공고 탐색 및 자소서 작성 업무 자동화 |
| 🎯 **정확성 향상** | 인재상 기반 자기소개서로 기업 맞춤화 지원 |
| 🔁 **반복 첨삭** | 첨삭 루프를 통해 품질 높은 자소서 완성 |
| 🖥 **사용자 친화적** | Django 기반 웹 UI로 접근성과 사용성 향상 |

---
