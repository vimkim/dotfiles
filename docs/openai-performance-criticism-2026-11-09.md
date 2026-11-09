# OpenAI 모델 성능 저하 비판 확인

조사 기준일은 2026년 11월 9일, 한국시각이다. 아래 게시일은 UTC로 통일했다. Reddit과 OpenAI 포럼의 날짜는 원문 JSON의 게시시각을 확인했다. 수치는 별도 표시가 없으면 출처 작성자의 측정이며, 이번 조사에서 재실험하지 않았다.

최근 공개 원문에는 코드 이해, 지시 이행, 응답 속도, 사용 한도에 대한 구체적인 불만이 있다. 다만 이 자료만으로 OpenAI 모델 전체가 지속적으로 퇴보했다고 결론 내릴 수는 없다.

이번 pstack 설정 변경의 목적은 비용 절감이다. Astra와 Sol 모두 체감 품질이 나빠졌다는 사용자 경험 아래, 비용 부담이 큰 Astra의 모든 역할을 GPT-6.1 Sol로 전환한다. 기존 Terra 역할과 `large (xhigh)` 추론 예산은 유지한다.

- 2026-10-13, Reddit 사용자 Hot_Season8992는 다섯 모델을 `xhigh`로 비교했다며 일반 모드에서 GPT-5.6 Sol은 102.6토큰/초, GPT-6.1 Sol은 22.3토큰/초였다고 보고했다. 제목의 "4.6배 느리다"는 이 생성 속도의 비율이다. 작업 전체의 완료 시간이나 정답률을 비교한 수치는 아니다. 작성자도 통제 실험이 아닌 개별 표본이며 의도적 속도 제한의 증거가 아니라고 명시했다. [속도 비교 원문](https://www.reddit.com/r/codex/comments/1x4yte1/gpt61_sol_is_46x_slower_than_gpt56_sol_are_we/)
- 2026-10-13, GitHub 사용자 fooklook은 Codex VS Code 확장에서 GPT-6.1 Sol, GPT-6 Astra, GPT-5.6 Sol 모두 코드 이해와 응답 속도가 나빠졌다고 보고했다. 같은 코드와 질문은 ChatGPT 웹에서 더 잘 처리됐다는 관찰도 남겼다. 비공개 코드와 실행 기록이 공개되지 않아 재현 여부는 확인할 수 없다. 작성자가 당일 이슈를 닫았으며, 공개 댓글에는 중복 후보를 안내하는 봇 응답만 있다. 종료 상태를 공식 원인 확인이나 해결 증거로 볼 수 없다. [openai/codex #53583](https://github.com/openai/codex/issues/53583)
- 2026-10-20, Reddit 사용자 Sea_Masterpiece4343는 본문에서 10월 21일의 경험을 설명하며 Astra가 요청하지 않은 메뉴를 추가하고 기존 UI를 재배치했다고 주장했다. 분석은 맞지만 구현이 요구와 어긋나고, 수정을 반복해도 비슷한 문제가 남았다는 내용이다. macOS 재설치 전후의 환경 차이도 인정했다. 모델 변경이나 의도적 품질 저하를 확인한 자료는 아니다. 게시일과 본문 사건일은 시간대에 따라 다르다. [Astra 지시 이행 불만 원문](https://www.reddit.com/r/codex/comments/1xb4dgf/im_a_200month_chatgpt_pro_subscriber_has_anyone/)
- 2026-10-25, Reddit 사용자 Defiant-Truck3는 임시 사용량 초기화가 제공되는 동안에도 주간 한도를 하루에 소진한다며, 행사가 끝나면 더 높은 요금제로 밀려날 것을 우려했다. 이 사례는 가격 대비 사용량에 대한 불만이다. 한도 소비가 빠르다는 사실만으로 모델의 추론 능력이나 정답률이 낮아졌다고 해석할 수는 없다. 게시물의 요금제 변경 주장은 공식 정책 확인 자료로 사용하지 않았다. [주간 사용 한도 불만 원문](https://www.reddit.com/r/codex/comments/1xfb5jb/guys_this_is_still_a_weekly_limit/)
- 2026-11-01, OpenAI 포럼 사용자 TomBob은 10월 29일부터 이미지 열 장을 요청해도 한 장만 받거나, 보존하라고 지정한 세부 사항이 바뀌고 수정 요청에는 같은 이미지가 반복된다고 보고했다. 후속 참여자도 비슷한 문제를 적었다. 반면 같은 스레드의 showaemergency는 사실적인 필름 이미지 표현은 개선됐지만 여러 장면의 인물 배치가 나빠졌다고 구분했다. 이미지 작업의 불만을 코딩 모델의 퇴보로 일반화할 수는 없다. [이미지 생성·지시 이행 원문](https://community.openai.com/t/chatgpt-image-generation-has-gotten-significantly-worse-since-october-29th-is-anyone-else-experiencing-this/1411701)

일시적인 서비스 장애는 공식 기록으로도 확인된다. OpenAI는 [GPT-6.1 Sol의 Codex·Work 성능 장애](https://status.openai.com/incidents/01M4T4ZCM54D3ZPTQXRSWFG0XS), [ChatGPT·Codex·API 성능 장애](https://status.openai.com/incidents/01M5E4G39TD1BW1QWHZG6RFA5H), [6.1 Sol API 성능 장애](https://status.openai.com/incidents/01M5YY4A3TQETEQ53DVSK8SW10)를 각각 복구 완료로 기록했다. 이 기록은 해당 장애의 존재를 뒷받침한다. 모든 품질 불만의 원인이 같거나 모델 가중치가 지속적으로 악화됐다는 증거는 아니다. 이력 화면과 상세 화면에 날짜가 하루 다르게 표시되어 상세 사건 링크를 기준으로 삼았다.

11월 9일 확인한 Artificial Analysis의 비교표에서, 이번 설정과 같은 `xhigh` 기준 작업당 비용은 Astra 3.66달러, Sol 6.1은 0.76달러다. 같은 표의 지능지수는 각각 55와 52, 작업당 시간은 11.6분과 9.2분이다. 이 평가에서는 Sol의 비용이 낮다. 이 값은 평가 과제에 대한 API 비용과 실행 시간이며, ChatGPT 구독 한도의 소비 비율이나 실제 저장소 작업의 비용을 보장하지 않는다. 두 모델의 비교표이므로 동일 모델의 시간에 따른 퇴보를 검사한 자료도 아니다. [Artificial Analysis 원본 비교표](https://artificialanalysis.ai/models/releases/comparisons/gpt-6-1-sol-vs-gpt-6-astra)

9월 9일 Entelligence의 50개 PR 평가에서는 확인된 결함 하나당 비용이 GPT-5.6 Sol 0.039달러, Astra 0.062달러였다. 반대로 보고한 지적의 정밀도는 Astra 95%, Sol 85%였고, 리뷰 시간도 Astra 36초, Sol 51초였다. 비용과 발견 건수를 중시할 때와 오탐·대기 시간을 중시할 때 선택이 달라진다. 작성자는 단일 실행, 인위적으로 주입한 결함, diff만 읽는 조건, 평가 모델의 편향 가능성을 한계로 밝혔다. 이 결과는 GPT-6.1 Sol의 우위를 검증한 실험도 아니다. [Entelligence 평가 원문](https://www.entelligence.ai/blogs/gpt-6-astra-cost-1.6x-more-per-verified-bug-than-gpt-5.6-sol)

커뮤니티 글은 불만의 구체적인 형태를 확인하는 자료다. 불만이 있는 사용자가 더 적극적으로 글을 쓰는 편향이 있고, 계정·시간대·문맥 길이·추론 강도·도구 환경을 통제하지 않았다. 따라서 불만의 전체 사용자 비율이나 지속적 성능 저하의 크기를 추정할 수 없다. 모델 전환의 효과는 실제 작업에서 같은 저장소 상태와 지시를 사용해 완료 품질, 수정 횟수, 경과 시간, 한도 소비를 함께 비교해야 판단할 수 있다.
